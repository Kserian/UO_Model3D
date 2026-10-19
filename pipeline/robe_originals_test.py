"""Phase 4 of docs/plans/original_items_calibration.md: loose garments (robes, dresses, skirts, kilts) on MANY originals instead of robe 469.

    python robe_originals_test.py <client dir> <out.json> [--jobs 3] [--srcs anim:469,anim3:432,...] [--arg "--follow thigh=0.9,0,1,0.5;shin=0.6,0,1,0.6"] [--actions ...]

Every original is extracted from the client into a temporary .vd (never into the repo) and run through `test_robe.py --derive` (the tube radii and the hem are measured on ITS stand pose),
with the same global parameters. Output per original: lower-body IoU, hem width error (wider / narrower), hem height error. The originals are split by position in the sorted list
(even = training, odd = held out) so that parameters can be fitted on one half and checked on the other.
"""
import json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "vdtool"))
import mul2vd                                                                       # noqa: E402

SRCS = ["anim:447", "anim:448", "anim:449", "anim:455", "anim:469", "anim:970", "anim:971", "anim:987", "anim3:432", "anim3:438", "anim3:441", "anim3:481",
        "anim4:443", "anim4:458", "anim4:505", "anim5:427", "anim5:632"]


def run(job):
    client, src, extra, actions, tmp = job
    tag, _, sid = src.partition(":")
    vd_dir = os.path.join(tmp, "vd")
    os.makedirs(vd_dir, exist_ok=True)
    mul2vd.extract(os.path.join(client, tag + ".idx"), os.path.join(client, tag + ".mul"), int(sid), os.path.join(vd_dir, "anim_%s.vd" % src.replace(":", "_")))
    out = os.path.join(tmp, src.replace(":", "_") + ".json")
    cmd = [sys.executable, os.path.join(HERE, "test_robe.py"), "--derive", "--sprite", os.path.join(vd_dir, "anim_%s.vd" % src.replace(":", "_")), "--out", out,
           "--tmp", os.path.join(tmp, src.replace(":", "_"))] + (["--actions", actions] if actions else []) + extra
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    if r.returncode or not os.path.exists(out):
        return src, None, (r.stdout + r.stderr)[-300:]
    return src, json.load(open(out))["result"], ""


def main():
    args = sys.argv[1:]
    jobs, srcs, extra, actions = 3, SRCS, [], None
    for opt in ("--jobs", "--srcs", "--arg", "--actions"):
        if opt in args:
            i = args.index(opt)
            v = args[i + 1]
            del args[i:i + 2]
            if opt == "--jobs":
                jobs = int(v)
            elif opt == "--srcs":
                srcs = v.split(",")
            elif opt == "--arg":
                extra += ["--follow", v] if not v.startswith("--") else v.split(None, 1)
            else:
                actions = v
    client, out = args
    tmp = tempfile.mkdtemp(prefix="robe_orig_")
    res = {}
    with ThreadPoolExecutor(jobs) as ex:
        for src, r, err in ex.map(run, [(client, s, extra, actions, tmp) for s in srcs]):
            res[src] = r
            print("%-10s %s" % (src, ("IoU low %.3f whole %.3f | hem wider %.2f narrower %.2f abs %.2f | hem y %.2f" % (r["iou_low"], r["iou_all"], r["hem_wider"], r["hem_narrower"], r["hem_abs"], r["hem_y_abs"])) if r else "FAILED " + err), flush=True)
    ok = sorted(s for s in res if res[s])
    split = {s: ("train" if i % 2 == 0 else "held") for i, s in enumerate(ok)}
    for part in ("train", "held"):
        v = [res[s]["iou_low"] for s in ok if split[s] == part]
        print("%-5s %2d  mean lower-body IoU %.4f" % (part, len(v), sum(v) / max(len(v), 1)))
    json.dump(dict(extra=extra, results=res, split=split), open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
