import re

with open("SAMANVAY_EL05_Architecture_v2_0.md", "r", encoding="utf-8") as f:
    text = f.read()

lines = text.splitlines()

output_lines = []
for i, line in enumerate(lines):
    if re.match(r"^#{1,3}\s", line):
        clean_line = line.encode("ascii", "replace").decode("ascii")
        output_lines.append(f"L{i+1}: {clean_line[:100]}")

with open("spec_headings.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))
print(f"Wrote {len(output_lines)} headings to spec_headings.txt")
