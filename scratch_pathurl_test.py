import re
from pathlib import Path

output_dir = Path("output")
candidates = [p for p in output_dir.iterdir() if p.name.endswith("_cut.xml")]
for p in candidates:
    print("candidate:", p.name)
src = next(p for p in candidates if "literal" not in p.name and "encoded" not in p.name and "LAVI" in p.name)
text = src.read_text(encoding="utf-8")
pathurls = re.findall(r"<pathurl>([^<]*)</pathurl>", text)
print("source:", src)
for p in pathurls:
    print("pathurl:", p)

video_pathurl = pathurls[0]
assert "input" in video_pathurl

# Variant A: 2 slashes after file: , drive letter directly follows (no empty leading slash before path)
variant_a = video_pathurl.replace("file:///C:/", "file://C:/")
# Variant B: explicit localhost authority
variant_b = video_pathurl.replace("file:///C:/", "file://localhost/C:/")

for name, new_pathurl in (("two_slash", variant_a), ("localhost", variant_b)):
    out_text = text.replace(video_pathurl, new_pathurl)
    out_path = output_dir / f"{src.stem}_{name}_variant.xml"
    out_path.write_text(out_text, encoding="utf-8", newline="\n")
    print(f"{name}: {new_pathurl}")
    print(f"  -> {out_path}")
