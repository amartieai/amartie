"""
Layer Local — Free, Self-Hosted JEV Fallback
==============================================
Same primitives as JEV (TypeSafe) but runs locally:
- Choice: Select one from a set
- Score: Rate on a scale
- Noul: Yes/no probability

No API key required. No network calls.
Uses deterministic rule engine for fail-closed evaluation.
"""

import hashlib
import json
import re
from typing import Dict, List, Optional, Any


class LayerChoice:
    """Choice question for Layer."""
    def __init__(self, instructions: str, criteria: Dict[str, str]):
        self.type = "choice"
        self.instructions = instructions
        self.criteria = criteria


class LayerScore:
    """Score question for Layer."""
    def __init__(self, instructions: str, criteria: List[str]):
        self.type = "score"
        self.instructions = instructions
        self.criteria = criteria


class LayerNoul:
    """Noul (yes/no) question for Layer."""
    def __init__(self, instructions: str, criteria: Optional[Dict[str, str]] = None):
        self.type = "noul"
        self.instructions = instructions
        self.criteria = criteria or {"true": "Yes", "false": "No"}


class LayerClient:
    """
    Free, self-hosted Layer client.
    
    Uses deterministic rule engine to evaluate actions.
    Can be extended to use local models (Ollama, llama.cpp, etc.)
    """
    
    def __init__(self):
        self.name = "layer-local"
        self.version = "0.1.0"
    
    def system_one(self, state: str, questions: Dict[str, Any]) -> 'LayerResponse':
        """
        Evaluate questions against the state.
        
        Args:
            state: The state string to evaluate
            questions: Dict of question name -> LayerChoice/LayerScore/LayerNoul
            
        Returns:
            LayerResponse with answers
        """
        answers = {}
        
        for name, question in questions.items():
            if isinstance(question, LayerChoice):
                answers[name] = self._evaluate_choice(state, question)
            elif isinstance(question, LayerScore):
                answers[name] = self._evaluate_score(state, question)
            elif isinstance(question, LayerNoul):
                answers[name] = self._evaluate_noul(state, question)
        
        return LayerResponse(answers=answers)
    
    def _evaluate_choice(self, state: str, question: LayerChoice) -> dict:
        """Evaluate a choice question."""
        # Simple rule: check if state contains keywords matching criteria
        state_lower = state.lower()
        scores = {}
        
        for key, description in question.criteria.items():
            # Score based on keyword presence and description relevance
            score = self._keyword_match(state_lower, key, description)
            scores[key] = score
        
        # Normalize scores to probabilities
        total = sum(scores.values())
        if total > 0:
            probabilities = {k: v / total for k, v in scores.items()}
        else:
            # Equal distribution if no match
            probabilities = {k: 1.0 / len(scores) for k in scores}
        
        # Select highest probability
        choice = max(probabilities, key=lambda k: probabilities[k])
        confidence = probabilities[choice]
        
        return {
            "type": "choice",
            "choice": choice,
            "probabilities": probabilities,
            "confidence": confidence
        }
    
    def _evaluate_score(self, state: str, question: LayerScore) -> dict:
        """Evaluate a score question."""
        # For confidence scoring, use number of findings
        # More keywords matched = higher confidence
        state_lower = state.lower()
        
        # Count positive indicators
        positive = sum(1 for word in ["verified", "complete", "sound", "aligned", "recoverable"] if word in state_lower)
        negative = sum(1 for word in ["error", "warning", "fail", "missing", "exceeds"] if word in state_lower)
        
        # Calculate raw score (0 to len(criteria)-1)
        max_score = len(question.criteria) - 1
        raw_score = max(0, min(max_score, positive - negative + 1))
        
        # Map to probabilities
        probabilities = {}
        for i, level in enumerate(question.criteria):
            if i == raw_score:
                probabilities[str(i)] = 0.6
            elif abs(i - raw_score) == 1:
                probabilities[str(i)] = 0.25
            else:
                probabilities[str(i)] = 0.15 / max(1, len(question.criteria) - 2)
        
        # Normalize
        total = sum(probabilities.values())
        probabilities = {k: v / total for k, v in probabilities.items()}
        
        return {
            "type": "score",
            "score": raw_score,
            "legend": {str(i): level for i, level in enumerate(question.criteria)},
            "probabilities": probabilities,
            "confidence": probabilities.get(str(raw_score), 0.5)
        }
    
    def _evaluate_noul(self, state: str, question: LayerNoul) -> dict:
        """Evaluate a yes/no question."""
        state_lower = state.lower()
        
        # Count evidence indicators
        evidence_words = ["verified", "confirmed", "evidence", "proof", "documented"]
        warning_words = ["warning", "error", "missing", "unverified", "unsubstantiated"]
        
        evidence_count = sum(1 for w in evidence_words if w in state_lower)
        warning_count = sum(1 for w in warning_words if w in state_lower)
        
        # Calculate probability
        total = evidence_count + warning_count
        if total == 0:
            noul = 0.5  # Neutral
        else:
            noul = evidence_count / total
        
        return {
            "type": "noul",
            "noul": noul
        }
    
    def _keyword_match(self, state: str, key: str, description: str) -> float:
        """Match keywords in state."""
        score = 0.0
        
        # Exact key match
        if key.lower() in state:
            score += 2.0
        
        # Description word matches
        desc_words = description.lower().split()
        for word in desc_words:
            if len(word) > 3 and word in state:
                score += 0.5
        
        # Base score
        score += 0.1
        
        return score


class LayerResponse:
    """Response from Layer evaluation."""
    
    def __init__(self, answers: Dict[str, Any]):
        self.answers = answers
    
    @property
    def choices(self) -> Dict[str, dict]:
        """Get choice answers."""
        return {k: v for k, v in self.answers.items() if v.get("type") == "choice"}
    
    @property
    def scores(self) -> Dict[str, dict]:
        """Get score answers."""
        return {k: v for k, v in self.answers.items() if v.get("type") == "score"}
    
    @property
    def nouls(self) -> Dict[str, dict]:
        """Get noul answers."""
        return {k: v for k, v in self.answers.items() if v.get("type") == "noul"}


# Convenience functions
def Choice(instructions: str, criteria: Dict[str, str]) -> LayerChoice:
    return LayerChoice(instructions, criteria)

def Score(instructions: str, criteria: List[str]) -> LayerScore:
    return LayerScore(instructions, criteria)

def Noul(instructions: str, criteria: Optional[Dict[str, str]] = None) -> LayerNoul:
    return LayerNoul(instructions, criteria)


# Singleton
layer_client = LayerClient()
