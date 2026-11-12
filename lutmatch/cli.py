"""Command-line interface.

    Lut match REFERENCE CLIP [CLIP ...] [-o OUTPUT_DIR] [--strength 0.8] [--lut-only]
    Lut apply LUT.cube CLIP [CLIP ...] [-o OUTPUT_DIR]
"""

import argparse
import os
import sys

from . import core


def _bar(name):
    last = [-1]

    def cb(p):
        pct = int(p * 100)
        if pct != last[0] and sys.stdout.isatty():
            last[0] = pct
            sys.stdout.write("\r  grading %s  %3d%%" % (name, pct))
            sys.stdout.flush()
    return cb


def _out_dir(args, path):
    return args.output or os.path.join(os.path.dirname(os.path.abspath(path)), "graded")


def main(argv=None):
    p = argparse.ArgumentParser(prog="lut", description="Match the colour of a clip to a reference and export a .cube LUT.")
    sub = p.add_subparsers(dest="cmd")
    m = sub.add_parser("match", help="make a LUT (and a graded copy) that matches each clip to the reference")
    m.add_argument("reference", help="photo or video with the look you want")
    m.add_argument("clips", nargs="+", help="photos, videos or folders to match")
    m.add_argument("-o", "--output", help="output folder (default: a 'graded' folder next to each clip)")
    m.add_argument("-s", "--strength", type=float, default=1.0, help="0 = untouched, 1 = full match (default 1)")
    m.add_argument("--keep-luma", action="store_true", help="match colour only, keep the clip's brightness and contrast")
    m.add_argument("--lut-only", action="store_true", help="write the .cube without a graded copy")
    m.add_argument("--codec", choices=core.CODECS, default="h264", help="codec for graded videos (default h264)")
    a = sub.add_parser("apply", help="grade clips with an existing .cube LUT")
    a.add_argument("lut")
    a.add_argument("clips", nargs="+")
    a.add_argument("-o", "--output", help="output folder (default: a 'graded' folder next to each clip)")
    a.add_argument("--codec", choices=core.CODECS, default="h264")
    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 1

    if args.cmd == "match":
        if not 0 <= args.strength <= 1:
            p.error("--strength must be between 0 and 1")
        if not os.path.isfile(args.reference) or not core.kind_of(args.reference):
            print("Reference must be a photo or video: " + args.reference)
            return 1
        try:
            ref_frames = core.load_frames(args.reference)
        except Exception as e:
            print("Couldn't read the reference: %s" % e)
            return 1
    else:
        try:
            table = core.read_cube(args.lut)
        except Exception as e:
            print("Couldn't read the LUT: %s" % e)
            return 1

    clips = [c for c in core.collect_files(args.clips)
             if args.cmd == "apply" or os.path.abspath(c) != os.path.abspath(args.reference)]
    if not clips:
        print("No supported photos or videos found.")
        return 1

    failures = 0
    for path in clips:
        print(path)
        out_dir = _out_dir(args, path)
        try:
            if args.cmd == "match":
                r = core.match(path, args.reference, out_dir, args.strength, args.keep_luma, args.codec,
                               args.lut_only, ref_frames=ref_frames, progress=_bar(os.path.basename(path)))
                if sys.stdout.isatty() and r.graded and core.kind_of(path) == "video":
                    print()
                print("  LUT    -> " + r.cube)
                if r.graded:
                    print("  graded -> " + r.graded)
            else:
                os.makedirs(out_dir, exist_ok=True)
                _, dst = core.output_paths(path, out_dir, args.codec)
                if core.kind_of(path) == "image":
                    core.grade_image(path, dst, table)
                else:
                    core.grade_video(path, dst, os.path.abspath(args.lut), args.codec, _bar(os.path.basename(path)))
                    if sys.stdout.isatty():
                        print()
                print("  graded -> " + dst)
        except Exception as e:
            print("  ! failed: %s" % e)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
