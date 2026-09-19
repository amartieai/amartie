#!/usr/bin/env python3
from bcc import BPF
import os
import signal
import sys

BPF_TEXT = r"""
BPF_HASH(egress, u64, u64);
int trace_connect(struct pt_regs *ctx, struct sock *sk) {
    u64 pid = bpf_get_current_pid_tgid();
    u64 ts = bpf_ktime_get_ns();
    egress.update(&pid, &ts);
    bpf_trace_printk("MARTIE: pid=%d outbound connect\n", pid >> 32);
    return 0;
}
"""


def main():
    if os.geteuid() != 0:
        print("Run as root")
        sys.exit(1)
    b = BPF(text=BPF_TEXT)
    b.attach_kprobe(event="tcp_connect", fn_name="trace_connect")
    print("MARTIE gate attached. Ctrl+C to detach.")

    def stop(sig, frame):
        b.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    while True:
        try:
            print(b.trace_fields()[5].decode().strip())
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
