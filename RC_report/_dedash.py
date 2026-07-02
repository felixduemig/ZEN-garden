"""Remove prose em-dashes (' --- ') from thesis sections.
Paired (parenthetical) em-dashes -> parentheses; single em-dash -> comma.
Safe: '%-----' dividers and '--' en-dashes/ranges have no surrounding spaces, so untouched."""
import re, glob, os

SEC = r"C:\Users\felix\Documents\GitHub\ST_Final_Report_Felix_Duemig\thesis\Sections"
pair = re.compile(r"\s+---\s+([^.]*?)\s+---\s+")   # X --- aside --- Y  ->  X (aside) Y
single = re.compile(r"\s+---\s+")                   # remaining single   ->  ,

total = 0
for f in sorted(glob.glob(os.path.join(SEC, "*.tex"))):
    s = open(f, encoding="utf-8").read()
    before = len(re.findall(r"\s+---\s+", s))
    if before == 0:
        continue
    s2 = pair.sub(r" (\1) ", s)
    s2 = single.sub(", ", s2)
    after = len(re.findall(r"\s+---\s+", s2))
    open(f, "w", encoding="utf-8").write(s2)
    total += before - after
    print(f"{os.path.basename(f)}: {before} -> {after}  (replaced {before - after})")
print("TOTAL prose em-dashes replaced:", total)
