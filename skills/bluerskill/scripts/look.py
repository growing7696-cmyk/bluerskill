"""bluerskill look — measure the rendered image, not the scene.

audit.py reads the .blend; it can't see a milky, clipped, muddy or badly framed picture. look.py
reads the pixels of a beauty render (display-referred PNG, after AgX) and, given a subject mask,
judges value range, clipping, subject/background separation and framing.

    blender -b --python look.py -- beauty.png [--mask silhouette.png] [--json]

preview.py calls this automatically after a beauty render (it renders the mask for you).
IDs continue reference/ai-tells.md. Score = 100 - penalties (H=10, M=5, L=2).
"""

import sys
import json
import colorsys

import bpy
import numpy as np

WEIGHT = {"H": 10, "M": 5, "L": 2}


def load(path):
    """PNG -> float array (h, w, 3) of display values 0-1, row 0 = top."""
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)[::-1, :, :3]


def _luma(rgb):
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def _sat(rgb):
    mx, mn = rgb.max(-1), rgb.min(-1)
    return np.where(mx > 1e-4, (mx - mn) / np.maximum(mx, 1e-4), 0)


def analyze(beauty, mask=None):
    """beauty / mask: paths. Mask = silhouette render (subject black on white) or white-on-black."""
    rgb = load(beauty)
    h, w, _ = rgb.shape
    L = _luma(rgb)
    findings = []

    def add(fid, sev, msg, fix=""):
        findings.append({"id": fid, "sev": sev, "msg": msg, "fix": fix})

    p = {k: float(np.percentile(L, k)) for k in (2, 50, 98)}
    clipped = float((rgb.max(-1) >= 0.995).mean())
    crushed = float((L <= 0.012).mean())
    span = p[98] - p[2]
    stats = {"size": [w, h], "luma_p": p, "clipped": clipped, "crushed": crushed, "span": span}

    if clipped > 0.004:
        add("R4", "M" if clipped < 0.03 else "H", f"{clipped:.1%} of pixels clipped to white",
            "lower exposure / key power; AgX should roll highlights off, not clip")
    if crushed > 0.03:
        add("R4", "M", f"{crushed:.1%} of pixels crushed to black", "raise fill / world, or lift exposure")
    if span < 0.42:
        add("R5", "M" if span < 0.32 else "L",
            f"flat, milky value range (2–98 % luma span {span:.2f}, want ≥ 0.45)",
            "stronger key:fill ratio (3:1–8:1), a darker background, or 'AgX - Medium High Contrast'")
    top = float(np.percentile(L, 99.5))
    stats["top"] = top
    if top < 0.72:
        add("R5", "M", f"no true highlights: the brightest 0.5 % of the frame is only {top:.2f}",
            "a brighter, smaller key; glossier hero material; a rim light that kisses an edge")
    if p[2] > 0.2 and p[50] > 0.6:
        add("R5", "M", f"washed out: darkest 2 % is {p[2]:.2f} with a bright median {p[50]:.2f} (lifted blacks)",
            "less fill / world, lower exposure; let shadows under and behind things go properly dark")
    if p[50] > 0.78:
        add("R5", "M", f"overexposed overall (median luma {p[50]:.2f})", "hz.color_management(exposure=-0.5)")
    elif p[50] < 0.1:
        add("R5", "L", f"very dark overall (median luma {p[50]:.2f}) — fine only if it's a night mood")
    mids = float(((L > 0.25) & (L < 0.75)).mean())
    stats["midtones"] = mids
    if mids > 0.9:
        add("R6", "L", f"{mids:.0%} midtones: no real darks or lights to organize the picture",
            "design a light / mid / dark value structure: dark ground or background, lit subject")

    sat = _sat(rgb)
    hot = sat > 0.6
    if hot.any():
        mx = rgb.max(-1)
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        d = np.maximum(mx - rgb.min(-1), 1e-4)
        hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6
        neon = float((hot & (hue > 0.45) & (hue < 0.95) & (L > 0.15)).mean())
        stats["neon"] = neon
        if neon > 0.12:
            add("L5", "M", f"{neon:.0%} of the frame is saturated cyan/blue/purple (neon look)",
                "motivated, temperature-based light colors")
    stats["sat_mean"] = float(sat.mean())

    if mask:
        m = load(mask)
        if m.shape[:2] != (h, w):
            ys = (np.arange(h) * m.shape[0] / h).astype(int)
            xs = (np.arange(w) * m.shape[1] / w).astype(int)
            m = m[ys][:, xs]
        ml = _luma(m)
        subj = ml < 0.5 if ml.mean() > 0.5 else ml > 0.5     # silhouette is black-on-white
        area = float(subj.mean())
        stats["subject_area"] = area
        if area < 0.002:
            add("C7", "H", "subject not visible in frame", "re-aim the camera: hz.camera_rig(hero)")
        else:
            ys, xs = np.nonzero(subj)
            cx, cy = xs.mean() / w, ys.mean() / h
            stats["subject_centroid"] = [float(cx), float(cy)]
            if area < 0.03:
                add("C7", "M", f"subject fills only {area:.1%} of the frame", "move in or use a longer lens")
            if abs(cx - 0.5) < 0.04 and abs(cy - 0.5) < 0.05:
                add("C2", "L", "subject's visual mass dead-center", "frame_offset ≈ 0.1–0.17 toward a third")
            edges = [subj[0].mean(), subj[-1].mean(), subj[:, 0].mean(), subj[:, -1].mean()]
            cut = sum(e > 0.15 for e in edges)
            if cut >= 2:
                add("C8", "L", f"subject cropped on {cut} frame edges", "pull back unless the crop is a choice")
            # separation: subject vs. its immediate surroundings (a ring around the mask)
            ring = _dilate(subj, max(4, int(0.03 * max(w, h)))) & ~subj
            if ring.sum() > 50:
                ls, lb = float(np.median(L[subj])), float(np.median(L[ring]))
                # hue/sat difference counts too (warm subject on cool ground separates without value)
                cs, cb = rgb[subj].mean(0), rgb[ring].mean(0)
                hs, ss, _ = colorsys.rgb_to_hsv(*cs)
                hb, sb, _ = colorsys.rgb_to_hsv(*cb)
                dh = min(abs(hs - hb), 1 - abs(hs - hb)) * min(ss, sb) * 2
                sep = float(abs(ls - lb) + dh)
                stats["separation"] = {"subject_luma": ls, "surround_luma": lb, "score": sep}
                if sep < 0.06:
                    add("R7", "M", f"subject merges with its surroundings (luma {ls:.2f} vs {lb:.2f})",
                        "rim light, darker/lighter ground, or a contrasting surface under the subject")
                elif sep < 0.1:
                    add("R7", "L", f"weak subject/background separation (luma {ls:.2f} vs {lb:.2f})",
                        "a touch of rim or a value shift behind the subject")
            # specular life: does anything on the subject actually catch a highlight?
            Ls = L[subj]
            hi = float(np.percentile(Ls, 99) - np.median(Ls))
            stats["subject_highlight_lift"] = hi
            if hi < 0.3:
                add("R8", "M", "no highlights on the subject (dead, matte-everything read)",
                    "bevels + glossier materials + something to reflect (hz.hdri_world) + a rim/kicker")

    penalty = sum(WEIGHT[f["sev"]] for f in findings)
    return {"score": max(0, 100 - penalty), "findings": findings, "stats": stats}


def _dilate(m, r):
    out = m.copy()
    step = max(1, r // 4)
    for dy in range(-r, r + 1, step):
        for dx in range(-r, r + 1, step):
            if dx * dx + dy * dy <= r * r:
                out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def report(res, path=""):
    print(f"\n=== bluerskill look {path} ===")
    s = res["stats"]
    p = s["luma_p"]
    print(f"score: {res['score']}/100   luma p2/p50/p98 {p[2]:.2f}/{p[50]:.2f}/{p[98]:.2f}   "
          f"clipped {s['clipped']:.2%}   crushed {s['crushed']:.2%}"
          + (f"   subject {s['subject_area']:.1%} of frame" if "subject_area" in s else ""))
    order = {"H": 0, "M": 1, "L": 2}
    for f in sorted(res["findings"], key=lambda f: order[f["sev"]]):
        print(f"  {f['sev']} {f['id']:<3} {f['msg']}")
        if f["fix"]:
            print(f"         fix: {f['fix']}")
    if not res["findings"]:
        print("  no pixel-level tells — still open the image and look at it.")
    print()


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        raise SystemExit("usage: blender -b --python look.py -- beauty.png [--mask silhouette.png] [--json]")
    mk = argv[argv.index("--mask") + 1] if "--mask" in argv else None
    r = analyze(argv[0], mk)
    if "--json" in argv:
        print("BLUERSKILL_LOOK_JSON " + json.dumps(r, default=float))
    else:
        report(r, argv[0])
