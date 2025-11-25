from fpdf import FPDF
import config

print(f"Testing font: {config.FONT_PATH}")

pdf = FPDF()
try:
    pdf.add_font('CustomFont', '', config.FONT_PATH)
    print("Font added successfully.")
except Exception as e:
    print(f"Error adding font: {e}")
    exit(1)

pdf.add_page()
pdf.set_font('CustomFont', size=16)

summary_text = """
# Meeting Summary

## Main Goals
* Verify the bot components.

## Key Ideas
* Use a script to test DB and PDF.
* Ensure Cyrillic support: Привет, мир!

## Action Items
* [ ] Run this script.

## Decisions Made
* Approved the plan.
"""

lines = summary_text.split('\n')
font_name = 'CustomFont'

try:
    pdf.multi_cell(0, 10, "Test Bullet: •")
    print("Bullet point worked.")
except Exception as e:
    print(f"Bullet point failed: {e}")

try:
    pdf.multi_cell(0, 10, "Test Cyrillic: Привет")
    print("Cyrillic worked.")
except Exception as e:
    print(f"Cyrillic failed: {e}")

for line in lines:
    try:
        if line.startswith('# '):
            # pdf.set_font(font_name, size=16)
            pdf.multi_cell(0, 10, line.replace('# ', ''))
            # pdf.set_font(font_name, size=12)
        elif line.startswith('## '):
            # pdf.set_font(font_name, size=14)
            pdf.ln(5)
            pdf.multi_cell(0, 10, line.replace('## ', ''))
            # pdf.set_font(font_name, size=12)
        elif line.startswith('* ') or line.startswith('- '):
            pdf.multi_cell(0, 8, f"  • {line[2:]}")
        else:
            pdf.multi_cell(0, 8, line)
    except Exception as e:
        print(f"Error processing line '{line}': {e}")

pdf.output("debug.pdf")
print("PDF saved.")
