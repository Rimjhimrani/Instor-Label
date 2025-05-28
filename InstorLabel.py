import streamlit as st
import pandas as pd
import os
import re
import datetime
from io import BytesIO
import tempfile

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, PageBreak, Image
from reportlab.lib.units import cm, inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# Define sticker dimensions
STICKER_WIDTH = 10 * cm
STICKER_HEIGHT = 15 * cm
STICKER_PAGESIZE = (STICKER_WIDTH, STICKER_HEIGHT)

# Define content box dimensions
CONTENT_BOX_WIDTH = 10 * cm
CONTENT_BOX_HEIGHT = 5 * cm

def normalize_column_name(col_name):
    """Normalize column names by removing all non-alphanumeric characters and converting to lowercase"""
    return re.sub(r'[^a-zA-Z0-9]', '', str(col_name)).lower()

def find_column(df, possible_names):
    """Find a column in the DataFrame that matches any of the possible names"""
    normalized_df_columns = {normalize_column_name(col): col for col in df.columns}
    normalized_possible_names = [normalize_column_name(name) for name in possible_names]

    for norm_name in normalized_possible_names:
        if norm_name in normalized_df_columns:
            return normalized_df_columns[norm_name]

    # Check for partial matches
    for norm_name in normalized_possible_names:
        for df_norm_name, original_name in normalized_df_columns.items():
            if norm_name in df_norm_name or df_norm_name in norm_name:
                return original_name

    # Check for line location keywords
    for df_norm_name, original_name in normalized_df_columns.items():
        if ('line' in df_norm_name and 'location' in df_norm_name) or 'lineloc' in df_norm_name:
            return original_name

    return None

def generate_qr_code(data_string):
    """Generate a QR code from the given data string"""
    try:
        import qrcode
        from PIL import Image as PILImage

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )

        qr.add_data(data_string)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white")

        img_buffer = BytesIO()
        qr_img.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        return Image(img_buffer, width=1.8*cm, height=1.8*cm)
    except Exception as e:
        st.error(f"Error generating QR code: {e}")
        return None

def parse_line_location(location_string):
    """Parse line location string and split into 4 boxes"""
    if not location_string or pd.isna(location_string):
        return ["", "", "", ""]

    parts = str(location_string).split("_")
    result = parts[:4] + [""] * (4 - len(parts))
    return result[:4]

def generate_sticker_labels(df, line_loc_header_width, line_loc_box1_width, 
                          line_loc_box2_width, line_loc_box3_width, line_loc_box4_width):
    """Generate sticker labels with QR code from DataFrame"""
    try:
        # Define column mappings
        column_mappings = {
            'ASSLY': ['assly', 'ASSY NAME', 'Assy Name', 'assy name', 'assyname',
                     'assy_name', 'Assy_name', 'Assembly', 'Assembly Name', 'ASSEMBLY', 'Assembly_Name'],
            'part_no': ['PARTNO', 'PARTNO.', 'Part No', 'Part Number', 'PartNo',
                       'partnumber', 'part no', 'partnum', 'PART', 'part', 'Product Code',
                       'Item Number', 'Item ID', 'Item No', 'item', 'Item'],
            'description': ['DESCRIPTION', 'Description', 'Desc', 'Part Description',
                           'ItemDescription', 'item description', 'Product Description',
                           'Item Description', 'NAME', 'Item Name', 'Product Name'],
            'Part_per_veh': ['QYT', 'QTY / VEH', 'Qty/Veh', 'Qty Bin', 'Quantity per Bin',
                            'qty bin', 'qtybin', 'quantity bin', 'BIN QTY', 'BINQTY',
                            'QTY_BIN', 'QTY_PER_BIN', 'Bin Quantity', 'BIN'],
            'Type': ['TYPE', 'type', 'Type', 'tyPe', 'Type name'],
            'line_location': ['LINE LOCATION', 'Line Location', 'line location', 'LINELOCATION',
                             'linelocation', 'Line_Location', 'line_location', 'LINE_LOCATION',
                             'LineLocation', 'line_loc', 'lineloc', 'LINELOC', 'Line Loc']
        }

        # Find columns
        found_columns = {}
        for key, possible_names in column_mappings.items():
            found_col = find_column(df, possible_names)
            if found_col:
                found_columns[key] = found_col

        # Check required columns
        required_columns = ['ASSLY', 'part_no', 'description']
        missing_required = [col for col in required_columns if col not in found_columns]

        if missing_required:
            st.error(f"Missing required columns: {missing_required}")
            return None, None

        # Create a temporary file for PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            output_pdf_path = tmp_file.name

        # Create PDF
        def draw_border(canvas, doc):
            canvas.saveState()
            x_offset = (STICKER_WIDTH - CONTENT_BOX_WIDTH) / 3
            y_offset = STICKER_HEIGHT - CONTENT_BOX_HEIGHT - 0.2*cm
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(1.5)
            canvas.rect(
                x_offset + doc.leftMargin,
                y_offset,
                CONTENT_BOX_WIDTH - 0.2*cm,
                CONTENT_BOX_HEIGHT
            )
            canvas.restoreState()

        doc = SimpleDocTemplate(output_pdf_path, pagesize=STICKER_PAGESIZE,
                              topMargin=0.2*cm,
                              bottomMargin=(STICKER_HEIGHT - CONTENT_BOX_HEIGHT - 0.2*cm),
                              leftMargin=0.1*cm, rightMargin=0.1*cm)

        # Define styles
        header_style = ParagraphStyle(name='HEADER', fontName='Helvetica-Bold', fontSize=10, alignment=TA_CENTER, leading=10)
        ASSLY_style = ParagraphStyle(name='ASSLY', fontName='Helvetica', fontSize=10, alignment=TA_LEFT, leading=16, spaceAfter=0, wordWrap='CJK', autoLeading="max")
        Part_style = ParagraphStyle(name='PART NO', fontName='Helvetica-Bold', fontSize=12, alignment=TA_LEFT, leading=46, spaceAfter=0, wordWrap='CJK', autoLeading="max")
        desc_style = ParagraphStyle(name='PART DESC', fontName='Helvetica', fontSize=8, alignment=TA_LEFT, leading=16, spaceAfter=0, wordWrap='CJK', autoLeading="max")
        partper_style = ParagraphStyle(name='Quantity', fontName='Helvetica', fontSize=10, alignment=TA_LEFT, leading=12)
        Type_style = ParagraphStyle(name='Quantity', fontName='Helvetica', fontSize=11, alignment=TA_LEFT, leading=12)
        date_style = ParagraphStyle(name='DATE', fontName='Helvetica', fontSize=10, alignment=TA_LEFT, leading=12)
        location_style = ParagraphStyle(name='Location', fontName='Helvetica', fontSize=9, alignment=TA_CENTER, leading=10)

        content_width = CONTENT_BOX_WIDTH - 0.2*cm
        all_elements = []
        today_date = datetime.datetime.now().strftime("%d-%m-%Y")

        # Process each row
        total_rows = len(df)
        progress_bar = st.progress(0)
        
        for index, row in df.iterrows():
            progress_bar.progress((index + 1) / total_rows)
            
            elements = []

            # Extract data
            ASSLY = str(row[found_columns.get('ASSLY', '')]) if 'ASSLY' in found_columns else "N/A"
            part_no = str(row[found_columns.get('part_no', '')]) if 'part_no' in found_columns else "N/A"
            desc = str(row[found_columns.get('description', '')]) if 'description' in found_columns else "N/A"
            Part_per_veh = str(row[found_columns.get('Part_per_veh', '')]) if 'Part_per_veh' in found_columns and pd.notna(row[found_columns['Part_per_veh']]) else ""
            Type = str(row[found_columns.get('Type', '')]) if 'Type' in found_columns and pd.notna(row[found_columns['Type']]) else ""
            line_location_raw = str(row[found_columns.get('line_location', '')]) if 'line_location' in found_columns and pd.notna(row[found_columns['line_location']]) else ""
            location_boxes = parse_line_location(line_location_raw)

            # Generate QR code
            qr_data = f"ASSLY: {ASSLY}\nPart No: {part_no}\nDescription: {desc}\n"
            if Part_per_veh:
                qr_data += f"QTY/BIN: {Part_per_veh}\n"
            if Type:
                qr_data += f"Type: {Type}\n"
            if line_location_raw:
                qr_data += f"Line Location: {line_location_raw}\n"
            qr_data += f"Date: {today_date}"

            qr_image = generate_qr_code(qr_data)
            if qr_image:
                qr_cell = qr_image
            else:
                qr_cell = Paragraph("QR", ParagraphStyle(name='QRPlaceholder', fontName='Helvetica-Bold', fontSize=12, alignment=TA_CENTER))

            # Define row heights
            ASSLY_row_height = 0.7*cm
            part_row_height = 0.7*cm
            desc_row_height = 0.7*cm
            bottom_row_height = 0.6*cm
            location_row_height = 0.6*cm

            # Process line location boxes
            location_box_1 = Paragraph(location_boxes[0], location_style) if location_boxes[0] else ""
            location_box_2 = Paragraph(location_boxes[1], location_style) if location_boxes[1] else ""
            location_box_3 = Paragraph(location_boxes[2], location_style) if location_boxes[2] else ""
            location_box_4 = Paragraph(location_boxes[3], location_style) if location_boxes[3] else ""

            # Create table data
            unified_table_data = [
                ["ASSLY", ASSLY],
                ["PART NO", part_no],
                ["PART DESC", desc],
                ["PART PER VEH", Paragraph(str(Part_per_veh), partper_style), qr_cell],
                ["TYPE", Paragraph(str(Type), Type_style), ""],
                ["DATE", Paragraph(today_date, date_style), ""],
                ["LINE LOCATION", location_box_1, location_box_2, location_box_3, location_box_4]
            ]

            # Create column widths
            col_widths_top = [content_width*0.3, content_width*0.7]
            col_widths_middle = [content_width*0.3, content_width*0.3, content_width*0.4]
            col_widths_bottom = [
                content_width * line_loc_header_width,
                content_width * line_loc_box1_width,
                content_width * line_loc_box2_width,
                content_width * line_loc_box3_width,
                content_width * line_loc_box4_width
            ]

            row_heights = [ASSLY_row_height, part_row_height, desc_row_height, bottom_row_height, bottom_row_height, bottom_row_height, location_row_height]

            # Create tables
            top_table = Table(unified_table_data[:3], colWidths=col_widths_top, rowHeights=row_heights[:3])
            middle_table = Table(unified_table_data[3:6], colWidths=col_widths_middle, rowHeights=row_heights[3:6])
            bottom_table = Table([unified_table_data[6]], colWidths=col_widths_bottom, rowHeights=[row_heights[6]])

            # Apply styles - UPDATED WITH CENTERED HEADERS
            top_style = [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 1), (1, 1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (0, -1), 11),
                ('FONTSIZE', (1, 0), (-1, 0), 10),
                ('FONTSIZE', (1, 1), (-1, 1), 11),
                ('FONTSIZE', (1, 2), (1, 2), 8),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Changed from 'LEFT' to 'CENTER'
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]

            middle_style = [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (0, 0), 9),  # Decreased font size for "PART PER VEH" from 11 to 9
                ('FONTSIZE', (0, 1), (0, 2), 11),  # Keep other headers at size 11
                ('FONTSIZE', (1, 0), (-1, -1), 11),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Changed from 'LEFT' to 'CENTER'
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('SPAN', (2, 0), (2, 2)),
            ]

            bottom_style = [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),  # Changed from 'LEFT' to 'CENTER' for header
                ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]

            # Apply styles to tables
            top_table.setStyle(TableStyle(top_style))
            middle_table.setStyle(TableStyle(middle_style))
            bottom_table.setStyle(TableStyle(bottom_style))

            # Add tables to elements
            elements.append(top_table)
            elements.append(middle_table)
            elements.append(bottom_table)

            # Add all elements for this sticker
            all_elements.extend(elements)

            # Add page break except for the last item
            if index < total_rows - 1:
                all_elements.append(PageBreak())

        # Build PDF
        doc.build(all_elements, onFirstPage=draw_border, onLaterPages=draw_border)
        
        # Read the PDF file to return as bytes
        with open(output_pdf_path, 'rb') as f:
            pdf_bytes = f.read()
        
        # Clean up temporary file
        os.unlink(output_pdf_path)
        
        return pdf_bytes, found_columns

    except Exception as e:
        st.error(f"Error generating PDF: {e}")
        return None, None

def main():
    st.set_page_config(
        page_title="Instor Label Generator",
        page_icon="🏷️",
        layout="wide"
    )
    
    st.title("🏷️ INSTOR LABEL GENERATOR")

    # Add the developer credit in smaller italic text on the left
    st.markdown(
        "<p style='font-size:14px; font-style:italic; margin-top:-10px; text-align:left;'>"
        "designed and developed by Agilomatrix</p>",
        unsafe_allow_html=True
    )

    st.markdown("---")
    
    # Sidebar for configuration
    st.sidebar.header("Configuration")
    st.sidebar.markdown("### Line Location Box Widths")
    st.sidebar.caption("(proportional values)")
    
    header_width = st.sidebar.number_input("Header Width", value=0.3, step=0.01, format="%.2f")
    box1_width = st.sidebar.number_input("Box 1 Width", value=0.2, step=0.01, format="%.2f")
    box2_width = st.sidebar.number_input("Box 2 Width", value=0.25, step=0.01, format="%.2f")
    box3_width = st.sidebar.number_input("Box 3 Width", value=0.15, step=0.01, format="%.2f")
    box4_width = st.sidebar.number_input("Box 4 Width", value=0.1, step=0.01, format="%.2f")
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📁 File Upload")
        uploaded_file = st.file_uploader(
            "Choose an Excel or CSV file",
            type=['xlsx', 'xls', 'csv'],
            help="Upload your data file containing label information"
        )
    
    with col2:
        st.header("📋 Preview & Generate")
        
        if uploaded_file is not None:
            try:
                # Load the data
                if uploaded_file.name.lower().endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.success(f"✅ File loaded successfully! ({len(df)} rows)")
                
                # Show file info
                with st.expander("📊 File Information", expanded=False):
                    st.write(f"**Total rows:** {len(df)}")
                    st.write(f"**Columns:** {list(df.columns)}")
                
                # Find columns
                column_mappings = {
                    'ASSLY': ['assly', 'ASSY NAME', 'Assy Name', 'assy name', 'assyname',
                             'assy_name', 'Assy_name', 'Assembly', 'Assembly Name', 'ASSEMBLY', 'Assembly_Name'],
                    'part_no': ['PARTNO', 'PARTNO.', 'Part No', 'Part Number', 'PartNo',
                               'partnumber', 'part no', 'partnum', 'PART', 'part', 'Product Code',
                               'Item Number', 'Item ID', 'Item No', 'item', 'Item'],
                    'description': ['DESCRIPTION', 'Description', 'Desc', 'Part Description',
                                   'ItemDescription', 'item description', 'Product Description',
                                   'Item Description', 'NAME', 'Item Name', 'Product Name'],
                    'Part_per_veh': ['QYT', 'QTY / VEH', 'Qty/Veh', 'Qty Bin', 'Quantity per Bin',
                                    'qty bin', 'qtybin', 'quantity bin', 'BIN QTY', 'BINQTY',
                                    'QTY_BIN', 'QTY_PER_BIN', 'Bin Quantity', 'BIN'],
                    'Type': ['TYPE', 'type', 'Type', 'tyPe', 'Type name'],
                    'line_location': ['LINE LOCATION', 'Line Location', 'line location', 'LINELOCATION',
                                     'linelocation', 'Line_Location', 'line_location', 'LINE_LOCATION',
                                     'LineLocation', 'line_loc', 'lineloc', 'LINELOC', 'Line Loc']
                }
                
                found_columns = {}
                for key, possible_names in column_mappings.items():
                    found_col = find_column(df, possible_names)
                    if found_col:
                        found_columns[key] = found_col
                
                # Show column mappings
                with st.expander("🔍 Column Mappings", expanded=False):
                    for key, col in found_columns.items():
                        st.write(f"**{key}:** {col}")
                
                # Check for required columns
                required_columns = ['ASSLY', 'part_no', 'description']
                missing_required = [col for col in required_columns if col not in found_columns]
                
                if missing_required:
                    st.error(f"⚠️ Missing required columns: {missing_required}")
                    st.info("Please ensure your file contains columns for Assembly, Part Number, and Description")
                else:
                    st.success("✅ All required columns found!")
                    
                    # Preview sample data
                    with st.expander("👀 Sample Data Preview", expanded=False):
                        sample_data = []
                        for i, (index, row) in enumerate(df.head(3).iterrows()):
                            row_data = {}
                            for key, col in found_columns.items():
                                row_data[key] = str(row[col]) if col in df.columns else "N/A"
                            sample_data.append(row_data)
                        
                        st.dataframe(pd.DataFrame(sample_data))
                    
                    # Generate PDF button
                    if st.button("🔄 Generate PDF Labels", type="primary", use_container_width=True):
                        with st.spinner("Generating PDF... Please wait"):
                            pdf_bytes, found_cols = generate_sticker_labels(
                                df, header_width, box1_width, box2_width, box3_width, box4_width
                            )
                            
                            if pdf_bytes:
                                st.success("🎉 PDF generated successfully!")
                                
                                # Create download button
                                filename = f"sticker_labels_{uploaded_file.name.split('.')[0]}.pdf"
                                st.download_button(
                                    label="📥 Download PDF",
                                    data=pdf_bytes,
                                    file_name=filename,
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                            else:
                                st.error("❌ Failed to generate PDF. Please check your data and try again.")
            
            except Exception as e:
                st.error(f"❌ Error loading file: {str(e)}")
        
        else:
            st.info("👆 Please upload a file to get started")
    
    # Instructions
    st.markdown("---")
    st.header("📖 Instructions")
    
    instructions_col1, instructions_col2 = st.columns(2)
    
    with instructions_col1:
        st.markdown("""
        ### 📋 Required Columns
        Your file must contain these columns (case-insensitive):
        - **Assembly** (ASSLY, Assembly Name, etc.)
        - **Part Number** (PARTNO, Part No, Item Number, etc.)
        - **Description** (DESCRIPTION, Part Description, etc.)
        """)
    
    with instructions_col2:
        st.markdown("""
        ### 📋 Optional Columns
        These columns will be included if found:
        - **Quantity per Vehicle** (QTY/VEH, Bin Quantity, etc.)
        - **Type** (TYPE, Type name, etc.)
        - **Line Location** (LINE LOCATION, Line Loc, etc.)
        """)
    
    st.markdown("""
    ### 🎯 Features
    - **QR Code Generation**: Each label includes a QR code with all relevant information
    - **Flexible Column Mapping**: Automatically detects various column name formats
    - **Customizable Layout**: Adjust line location box widths via sidebar
    - **Professional Format**: Ready-to-print PDF labels with proper formatting
    """)

if __name__ == "__main__":
    main()
