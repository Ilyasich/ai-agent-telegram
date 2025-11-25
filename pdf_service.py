from fpdf import FPDF
import os
import config
from datetime import datetime

def ensure_font():
    """Check if font exists."""
    if not os.path.exists(config.FONT_PATH):
        print(f"Warning: Font file {config.FONT_PATH} not found.")

def generate_pdf(summary_text, filename):
    """Generate PDF with Unicode support for Cyrillic."""
    
    pdf = FPDF()
    
    # Add Unicode font - DejaVu supports Cyrillic
    font_name = "DejaVu"
    try:
        # Use uni=True for Unicode support
        pdf.add_font(font_name, '', config.FONT_PATH, uni=True)
        pdf.add_font(font_name, 'B', config.FONT_PATH, uni=True)  # Same file for bold
    except Exception as e:
        print(f"Error loading font: {e}")
        # Fallback - just skip Cyrillic text
        font_name = "Arial"
    
    pdf.add_page()
    pdf.set_font(font_name, size=12)
    
    # Header
    pdf.set_font(font_name, size=10)
    try:
        pdf.cell(0, 10, f'Chat Summary - {datetime.now().strftime("%Y-%m-%d %H:%M")}', align='R')
    except:
        pdf.cell(0, 10, 'Chat Summary', align='R')
    pdf.ln(10)
    
    # Title
    pdf.set_font(font_name, 'B' if font_name == "DejaVu" else '', size=16)
    pdf.cell(0, 10, "Meeting Summary", ln=True, align='C')
    pdf.ln(10)
    
    # Body
    pdf.set_font(font_name, size=12)
    
    # Process line by line
    lines = summary_text.split('\n')
    
    for line in lines:
        # Skip empty lines
        if not line.strip():
            pdf.ln(5)
            continue
        
        try:
            # Handle markdown headers
            if line.startswith('# '):
                pdf.set_font(font_name, 'B' if font_name == "DejaVu" else '', size=16)
                pdf.cell(0, 10, line.replace('# ', ''), ln=True)
                pdf.set_font(font_name, size=12)
            elif line.startswith('## '):
                pdf.ln(3)
                pdf.set_font(font_name, 'B' if font_name == "DejaVu" else '', size=14)
                pdf.cell(0, 10, line.replace('## ', ''), ln=True)
                pdf.set_font(font_name, size=12)
            elif line.startswith('### '):
                pdf.set_font(font_name, 'B' if font_name == "DejaVu" else '', size=12)
                pdf.cell(0, 8, line.replace('### ', ''), ln=True)
                pdf.set_font(font_name, size=12)
            elif line.startswith('* ') or line.startswith('- '):
                # Indent and add bullet
                pdf.cell(10, 6, '', ln=False)
                pdf.cell(0, 6, '- ' + line[2:], ln=True)
            else:
                # Regular text
                pdf.cell(0, 6, line, ln=True)
        except Exception as e:
            # If a line fails (e.g., unsupported characters), skip it
            print(f"Skipping line due to error: {e}")
            continue
            
    pdf.output(filename)
    return filename
