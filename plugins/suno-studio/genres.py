"""
AMARTIE Music Genre Presets
============================
Pre-fabricated musical styles for the Suno Studio plugin.
Each preset is a carefully crafted prompt that produces consistent, high-quality results.
Built by the design crew — tested, refined, and proven.
"""

GENRE_PRESETS = {
    "country": {
        "name": "Country",
        "emoji": "🤠",
        "tags": "country, acoustic guitar, twang, storytelling, male vocals",
        "prompt_template": "A {mood} country song about {theme}. {details}. Acoustic guitar, pedal steel, warm male vocals, storytelling lyrics.",
        "moods": ["heartfelt", "upbeat", "melancholic", "nostalgic", "rowdy"],
        "example": "A heartfelt country song about driving home for Christmas. Missing family, open roads, cold night."
    },
    "blues": {
        "name": "Blues",
        "emoji": "🎸",
        "tags": "blues, electric guitar, soul, raw emotion, slow tempo",
        "prompt_template": "A {mood} blues track about {theme}. {details}. Electric guitar, Hammond organ, deep soulful vocals, 12-bar blues progression.",
        "moods": ["gritty", "smooth", "heartbroken", "late night", "swagger"],
        "example": "A gritty blues track about losing everything and starting over. Slow burn, raw emotion, Chicago style."
    },
    "jazz": {
        "name": "Jazz",
        "emoji": "🎷",
        "tags": "jazz, saxophone, piano, improvisation, swing",
        "prompt_template": "A {mood} jazz piece about {theme}. {details}. Saxophone, upright bass, brushed drums, piano improvisation.",
        "moods": ["smooth", "bebop", "cool", "late night", "upscale"],
        "example": "A smooth jazz piece about a rainy city at night. Cigarette smoke, neon reflections, walking alone."
    },
    "reggae": {
        "name": "Reggae",
        "emoji": "🌴",
        "tags": "reggae, offbeat, bass heavy, island vibes, male vocals",
        "prompt_template": "A {mood} reggae track about {theme}. {details}. Offbeat rhythm, heavy bass, steel drums, laid-back island vocals.",
        "moods": ["laid-back", "roots", "lovers rock", "dub", "conscious"],
        "example": "A laid-back reggae track about sunshine and good vibes. Beach, palm trees, no worries."
    },
    "lounge": {
        "name": "Lounge",
        "emoji": "🍸",
        "tags": "lounge, chill, sophisticated, bossa nova, cocktail",
        "prompt_template": "A {mood} lounge track about {theme}. {details}. Bossa nova guitar, soft brushes, Rhodes piano, breathy female vocals.",
        "moods": ["sophisticated", "chill", "romantic", "cocktail", "sunset"],
        "example": "A sophisticated lounge track about a rooftop bar at sunset. City skyline, cocktails, conversation."
    },
    "electronic": {
        "name": "Electronic",
        "emoji": "🎛️",
        "tags": "electronic, synth, dance, drops, build-ups",
        "prompt_template": "A {mood} electronic track about {theme}. {details}. Synthesizers, heavy drops, sidechain compression, club ready.",
        "moods": ["euphoric", "dark", "hypnotic", "futuristic", "aggressive"],
        "example": "A euphoric electronic track about losing yourself in the crowd. Pulsing synths, massive drop, hands in the air."
    },
    "classical": {
        "name": "Classical",
        "emoji": "🎻",
        "tags": "classical, orchestra, strings, piano, cinematic",
        "prompt_template": "A {mood} classical piece about {theme}. {details}. Full orchestra, sweeping strings, piano, cinematic dynamics.",
        "moods": ["epic", "tragic", "serene", "triumphant", "haunting"],
        "example": "An epic classical piece about a hero's journey. Strings swell, brass fanfare, timpani rolls."
    },
    "hiphop": {
        "name": "Hip-Hop",
        "emoji": "🎤",
        "tags": "hip-hop, rap, 808s, trap, bars",
        "prompt_template": "A {mood} hip-hop track about {theme}. {details}. 808 bass, hi-hats, trap flow, confident male rap vocals.",
        "moods": ["confident", "street", "introspective", "party", "grimey"],
        "example": "A confident hip-hop track about making it against all odds. Hard 808s, trap hats, storytelling bars."
    },
    "rock": {
        "name": "Rock",
        "emoji": "🤘",
        "tags": "rock, electric guitar, drums, powerful, anthemic",
        "prompt_template": "A {mood} rock track about {theme}. {details}. Distorted electric guitars, driving drums, powerful male vocals, anthemic chorus.",
        "moods": ["anthemic", "raw", "melodic", "punk", "arena"],
        "example": "An anthemic rock track about breaking free. Power chords, driving beat, crowd singalong chorus."
    },
    "latin": {
        "name": "Latin",
        "emoji": "💃",
        "tags": "latin, salsa, reggaeton, percussion, Spanish vocals",
        "prompt_template": "A {mood} latin track about {theme}. {details}. Congas, timbales, brass, reggaeton beat, passionate Spanish vocals.",
        "moods": ["passionate", "fiesta", "romantic", "street", "tropical"],
        "example": "A passionate latin track about dancing until dawn. Salsa rhythm, brass hits, Spanish guitar."
    },
    "ambient": {
        "name": "Ambient",
        "emoji": "🌊",
        "tags": "ambient, atmospheric, drones, pads, meditative",
        "prompt_template": "A {mood} ambient piece about {theme}. {details}. Long drones, reverb pads, field recordings, no percussion, immersive.",
        "moods": ["ethereal", "dark", "underwater", "space", "forest"],
        "example": "An ethereal ambient piece about floating in space. Endless reverb, slow evolution, no rhythm."
    },
    "celtic": {
        "name": "Celtic",
        "emoji": "🍀",
        "tags": "celtic, irish, fiddle, folk, storytelling",
        "prompt_template": "A {mood} celtic track about {theme}. {details}. Fiddle, tin whistle, bodhran, acoustic guitar, Irish female vocals.",
        "moods": ["mythic", "reverent", "raving", "ancient", "misty"],
        "example": "A mythic celtic track about an ancient forest. Fiddle, flute, Gaelic whispers, misty morning."
    },
    "funk": {
        "name": "Funk",
        "emoji": "🕺",
        "tags": "funk, slap bass, horns, groove, wah guitar",
        "prompt_template": "A {mood} funk track about {theme}. {details}. Slap bass, horn section, wah guitar, tight drum groove.",
        "moods": ["groovy", "flashy", "tight", "sloppy", "nasty"],
        "example": "A groovy funk track about a Saturday night party. Slap bass, horn stabs, wah guitar, tight groove."
    },
    "soul": {
        "name": "Soul",
        "emoji": "💋",
        "tags": "soul, rnb, vocals, emotion, groove",
        "prompt_template": "A {mood} soul track about {theme}. {details}. Female vocals, Hammond organ, Rhodes, real drums, emotional delivery.",
        "moods": ["sultry", "heartfelt", "powerful", "smooth", "gritty"],
        "example": "A sultry soul track about a late-night confession. Female vocals, organ swells, emotional dynamics."
    },
    "metal": {
        "name": "Metal",
        "emoji": "⚡",
        "tags": "metal, heavy, double bass, distorted, aggressive",
        "prompt_template": "A {mood} metal track about {theme}. {details}. Heavy distortion, double bass drums, aggressive male vocals, breakdown.",
        "moods": ["brutal", "epic", "technical", "doom", "thrash"],
        "example": "A brutal metal track about inner demons. Blast beats, breakdown, guttural vocals, heavy riffing."
    },
    "folk": {
        "name": "Folk",
        "emoji": "🪕",
        "tags": "folk, acoustic, banjo, harmonica, campfire",
        "prompt_template": "A {mood} folk song about {theme}. {details}. Acoustic guitar, banjo, harmonica, group vocals, campfire feel.",
        "moods": ["rustic", "political", "nostalgic", "protest", "wanderer"],
        "example": "A rustic folk song about a long journey home. Banjo, harmonica, group singalong, front porch."
    },
    "disco": {
        "name": "Disco",
        "emoji": "🪩",
        "tags": "disco, four-on-the-floor, strings, funky, dance",
        "prompt_template": "A {mood} disco track about {theme}. {details}. Four-on-the-floor, string section, funky bass, soaring vocals.",
        "moods": ["glamorous", "euphoric", "funky", "retro", "studio 54"],
        "example": "A glamorous disco track about a night at the club. Strings, falsetto, four-on-the-floor, glitter."
    },
    "bach_meets_blues": {
        "name": "Bach Meets Blues",
        "emoji": "🎹",
        "tags": "classical, blues, counterpoint, piano, fusion",
        "prompt_template": "A fusion of Bach-style counterpoint and Chicago blues. {theme}. {details}. Piano, Hammond organ, complex harmonies, bluesy improvisation over baroque structures.",
        "moods": ["intellectual", "soulful", "complex", "unexpected", "masterful"],
        "example": "A fusion of Bach counterpoint and Chicago blues. Piano left hand baroque, right hand blues improvisation."
    },
    "beethoven_meets_reggae": {
        "name": "Beethoven Meets Reggae",
        "emoji": "🏛️🌴",
        "tags": "classical, reggae, orchestral, offbeat, fusion",
        "prompt_template": "A fusion of Beethoven-style orchestral and Jamaican reggae. {theme}. {details}. Full orchestra meets offbeat reggae rhythm, strings with skank guitar, dramatic meets laid-back.",
        "moods": ["epic", "island", "contrast", "genius", "unexpected"],
        "example": "A fusion of Beethoven's 5th and roots reggae. Orchestral hits on the offbeat, dramatic strings with one-drop rhythm."
    },
    "texas_holdem_rock": {
        "name": "Texas Hold'em Rock",
        "emoji": "🤠🃏",
        "tags": "rock, country, blues, gambling, Texas, storytelling",
        "prompt_template": "A Texas hold'em poker rock anthem. {theme}. {details}. Pedal steel, distorted guitar, poker metaphors, bluffing, all-in, Texas night.",
        "moods": ["gritty", "gambling", "Texas", "late night", "all-in"],
        "example": "A Texas hold'em rock anthem about going all-in on a bluff. Pedal steel, distorted guitar, smoky casino."
    },
    "cyberpunk_jazz": {
        "name": "Cyberpunk Jazz",
        "emoji": "🌃🎷",
        "tags": "jazz, electronic, cyberpunk, synth, noir",
        "prompt_template": "A cyberpunk jazz piece about {theme}. {details}. Saxophone through distortion, synth bass, glitched drums, neon noir, rain-slicked streets.",
        "moods": ["noir", "neon", "rainy", "dystopian", "late night"],
        "example": "A cyberpunk jazz piece about a detective in a neon city. Distorted sax, synth bass, glitched drums."
    }
}


def get_preset(genre: str) -> dict:
    """Get a genre preset by name."""
    return GENRE_PRESETS.get(genre.lower(), GENRE_PRESETS["blues"])


def list_presets() -> list:
    """List all available presets."""
    return [
        {"id": k, "name": v["name"], "emoji": v["emoji"], "tags": v["tags"]}
        for k, v in GENRE_PRESETS.items()
    ]


def generate_prompt(genre: str, theme: str, details: str = "", mood: str = "") -> dict:
    """Generate a full prompt from a preset."""
    preset = get_preset(genre)
    if not mood:
        mood = preset["moods"][0]
    
    prompt = preset["prompt_template"].format(
        theme=theme,
        details=details,
        mood=mood
    )
    
    return {
        "prompt": prompt,
        "tags": preset["tags"],
        "title": f"{preset['name']}: {theme[:30]}",
        "model": "suno-v5",
        "genre": genre
    }
