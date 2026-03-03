import os
import re
from io import BytesIO
from google.cloud import storage
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
import gcsfs
fs = gcsfs.GCSFileSystem()
from .styles_config import get_styles, get_page_settings, get_image_settings, get_table_styles, get_brand_colors, get_header_footer_settings, add_page_decor # MAX_IMAGE_WIDTH_RATIO, MAX_IMAGE_HEIGHT

class GCSJSONToPDF:
    def __init__(self, bucket_name="acn-cda-adk-staging", output_dir="./reports", logo_path=None, cora_logo_path=None):
        self.bucket_name = bucket_name
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(bucket_name)

        # Load styles and settings from updated config
        self.styles = get_styles()
        self.page_width, self.page_height, self.margins, self.available_width, self.available_height = get_page_settings()
        self.image_settings = get_image_settings()
        self.table_styles = get_table_styles()
        self.brand_colors = get_brand_colors()
        self.header_footer_settings = get_header_footer_settings()
        
        # Set logo paths (either provided or default logos)
        # self.logo_path = logo_path or r"C:\Users\rasheena.a.t\OneDrive - Accenture\Documents\RMN\rmn_agent_work\data_science\sub_agents\phase1_report gen\Phase_1\Accenture_Logo.png"
        # self.cora_logo_path = cora_logo_path or r"C:\Users\rasheena.a.t\OneDrive - Accenture\Documents\RMN\rmn_agent_work\data_science\sub_agents\phase1_report gen\Phase_1\Cora.png"
        self.logo_path = logo_path or "gs://acn-cda-adk-staging/shared_docs/Accenture_Logo.png"
        self.cora_logo_path = cora_logo_path or "gs://acn-cda-adk-staging/shared_docs/Cora.png"

    def generate_acronym(self, title: str) -> str:
        """Generate acronym from a title string."""
        if not title or not isinstance(title, str):
            return ""
        return ''.join(word[0].upper() for word in title.strip().split() if word and word[0].isalpha())

    def _load_logo_as_bytesio(self, logo_path):
        """Load a logo file from disk and return as BytesIO object."""
        # if not logo_path or not os.path.exists(logo_path):
        #     print(f"⚠️ Logo file does not exist: {logo_path}")
        #     return None
        
        try:
            with fs.open(logo_path, 'rb') as f:
                logo_bytes = f.read()
            return BytesIO(logo_bytes)
        except Exception as e:
            print(f"⚠️ Could not load logo from {logo_path}: {e}")
            return None

    def _download_image_from_gcs(self, blob_path):
        """Download image from GCS using the blob path (no gs:// expected)."""
        try:
            blob = self.bucket.blob(blob_path)

            if not blob.exists():
                print(f"⚠️ Image not found in GCS: {blob_path}")
                return None

            image_data = BytesIO()
            blob.download_to_file(image_data)
            image_data.seek(0)

            img = Image(image_data)

            # Use image settings from config
            max_width = self.image_settings['max_width']
            max_height = self.image_settings['max_height']
            
            # Get original aspect ratio
            aspect_ratio = img.drawWidth / img.drawHeight

            # For very wide images (aspect ratio > 3), always use full width
            if aspect_ratio > 3:
                img.drawWidth = max_width
                img.drawHeight = max_width / aspect_ratio
            else:
                # For normal images, try to fit to max width first
                new_width = max_width
                new_height = new_width / aspect_ratio
                
                # Only scale down by height if the resulting height is too tall
                if new_height > max_height:
                    new_height = max_height
                    new_width = new_height * aspect_ratio
                
                img.drawWidth = new_width
                img.drawHeight = new_height

            img.hAlign = 'CENTER'
            return img

        except Exception as e:
            print(f"❌ Error loading image from GCS path '{blob_path}': {e}")
            return None

    def _process_text(self, story, text, style_name='body_style'):
        """Process text with proper formatting, bold support, and bullet points."""
        if not text or not isinstance(text, str):
            return
        print(f"Processing text block:{text}, with type: {type(text)}")
        for para in text.split('\n'):
            para = para.strip()
            if not para:
                continue
                
            # Convert markdown bullets (* or - followed by space) to proper bullets
            if re.match(r'^(\*|-)\s+', para):
                para = re.sub(r'^(\*|-)\s+', '• ', para)
                current_style = self.styles.get('bullet_style', self.styles['body_style'])
            else:
                current_style = self.styles[style_name]
            
            # Convert markdown bold (**) to ReportLab bold tags
            para = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', para)
            
            story.append(Paragraph(para, current_style))

    def _process_table(self, story, table_obj):
        """Process table with Accenture brand styling."""
        if 'title' in table_obj:
            story.append(Paragraph(table_obj['title'], self.styles['subsection_header_style']))
            story.append(Spacer(1, 8))
        content = table_obj.get('table_content', {})
        headers = content.get('headers', [])
        rows = content.get('rows', [])
        
        if not headers:
            print("⚠️ Table has no headers, skipping.")
            return
        
        # Build table data
        # Split into two halves if columns > 12
        if len(headers) > 12:
            mid = len(headers) // 2 + len(headers) % 2  # Divide columns in half (round up)

            header_splits = [headers[:mid], headers[mid:]]
            row_splits = [
                [row[:mid] for row in rows],
                [row[mid:] for row in rows]
            ]
        else:
            header_splits = [headers]
            row_splits = [rows]

        # Build and append tables
        for split_headers, split_rows in zip(header_splits, row_splits):
            wrapped_headers = [Paragraph(str(h), self.styles['table_header_style']) for h in split_headers]
            wrapped_data = [
                [Paragraph(str(cell), self.styles['table_cell_style']) for cell in row]
                for row in split_rows
            ]

            data = [wrapped_headers] + wrapped_data
            col_width = self.available_width / len(split_headers)

            table = Table(data, colWidths=[col_width]*len(split_headers), repeatRows=1)
            table.setStyle(self.table_styles['default_table_style'])

            story.append(Spacer(1, 12))
            story.append(table)
            story.append(Spacer(1, 8))

      
      
        # Add caption if present (centered below table)
        if table_obj.get('caption'):
            caption_text = f"Table: {table_obj['caption']}"
            story.append(Paragraph(caption_text, self.styles['caption_style']))
            story.append(Spacer(1, 12))
        
        # Add source attribution if present
        if table_obj.get('source'):
            source_text = f"Source: {table_obj['source']}"
            story.append(Paragraph(source_text, self.styles['source_style']))
            story.append(Spacer(1, 8))

    def _process_visuals(self, story, visuals):
        """Process visual elements (charts/images) with captions and source attribution."""
        # Handle dict or list inputs for visuals
        if isinstance(visuals, dict):
            visuals = [visuals]  # wrap single dict into list for uniform processing
        
        if not isinstance(visuals, list):
            print(f"⚠️ Unexpected visuals type: {type(visuals)}. Skipping visuals.")
            return

        for idx, visual in enumerate(visuals, start=1):
            if isinstance(visual, dict):
                blob_path = visual.get('chart_link', '').strip()
                if not blob_path:
                    blob_path = visual.get('image', '').strip()  # Try 'image' key as fallback
                caption = visual.get('caption', '')
                if not caption:
                    caption = visual.get('subtitle', '')  # Try 'subtitle' key as fallback
                source = visual.get('source', '')
                insight = visual.get('insight', '')  # Business insight connecting to outcomes
            elif isinstance(visual, str):
                # Just a string path, no caption
                blob_path = visual.strip()
                caption = ''
                source = ''
                insight = ''
            else:
                print(f"⚠️ Unexpected visual item type: {type(visual)} - {visual}")
                continue

            if not blob_path:
                print(f"⚠️ No chart_link/image found in visual: {visual}")
                continue

            # Remove "gs://" prefix if present for blob path
            if blob_path.startswith("gs://"):
                print(f"Visual blob path starts with 'gs://', stripping prefix for GCS access: {blob_path}, type: {type(blob_path)}")
                parts = blob_path.split("/", 3)
                if len(parts) >= 4:
                    blob_path = parts[3]

            # Add spacing before image
            story.append(Spacer(1, self.image_settings['default_spacing_before']))
            
            # Download and add image
            img = self._download_image_from_gcs(blob_path)
            if img:
                story.append(img)
                story.append(Spacer(1, self.image_settings['default_spacing_after']))
            else:
                story.append(Paragraph(f"[Image missing: {blob_path}]", self.styles['body_style']))
                story.append(Spacer(1, 6))

            # Add caption (centered, labeled as Figure X)
            if caption:
                caption_text = f"Figure {idx}: {caption}"
                story.append(Paragraph(caption_text, self.styles['caption_style']))
                story.append(Spacer(1, 6))
            
            # Add source attribution (for traceability)
            if source:
                source_text = f"Source: {source}"
                story.append(Paragraph(source_text, self.styles['source_style']))
                story.append(Spacer(1, 6))
            
            # Add business insight (connects metrics to outcomes)
            if insight:
                story.append(Paragraph(insight, self.styles['insight_style']))
                story.append(Spacer(1, 12))

    def _process_callout(self, story, callout_text):
        """Process callout/highlight boxes for executive summaries or key metrics."""
        if not callout_text:
            return
        story.append(Spacer(1, 12))
        story.append(Paragraph(callout_text, self.styles['callout_style']))
        story.append(Spacer(1, 12))

    def _process_executive_summary(self, story, summary_text):
        """Process executive summary with centered, emphasized styling."""
        if not summary_text:
            return
        story.append(Spacer(1, 16))
        story.append(Paragraph(summary_text, self.styles['executive_summary_style']))
        story.append(Spacer(1, 16))

    def _process_section(self, story, key, value, level=0):
        """Recursively process JSON sections into PDF elements."""
        # Determine appropriate header style based on nesting level
        if level == 0:
            style = 'title_style'
        elif level == 1:
            style = 'section_header_style'
        elif level == 2:
            style = 'subsection_header_style'
        else:
            style = 'chart_title_style'
        
        # Add section header
        header_text = key.replace("_", " ").title()
        story.append(Paragraph(header_text, self.styles[style]))
        story.append(Spacer(1, 8))

        # Process value based on type
        if isinstance(value, dict):
            # Check for special keys first
            if 'executive_summary' in value:
                self._process_executive_summary(story, value['executive_summary'])
            
            if 'callout' in value:
                self._process_callout(story, value['callout'])
            
            # Process all dict items
            for subkey, subval in value.items():
                if subkey == 'executive_summary' or subkey == 'callout':
                    continue  # Already processed above
                elif subkey.startswith("text") and isinstance(subval, str):
                    self._process_text(story, subval)
                    story.append(Spacer(1, 8))
                elif subkey.startswith("table") and isinstance(subval, dict):
                    self._process_table(story, subval)
                elif subkey.startswith("image") or subkey.startswith("visual"):
                    self._process_visuals(story, subval)
                elif subkey not in ['chart_link', 'caption', 'source', 'insight']:
                    # Treat everything else as a subsection (recursively)
                    self._process_section(story, subkey, subval, level + 1)

        elif isinstance(value, str):
            self._process_text(story, value)
            story.append(Spacer(1, 8))

        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    for k, v in item.items():
                        self._process_section(story, k, v, level + 1)
                else:
                    self._process_text(story, str(item))
                    story.append(Spacer(1, 6))

        # Add spacing after sections
        if level <= 1:
            story.append(Spacer(1, 10))

    def generate_pdf(self, json_input, output_filename="report.pdf", logo_path=None, cora_logo_path=None, gcs_pdf_path = None):
        """Generate PDF from JSON input with Accenture branding and dual logos."""
        import json

        output_path = os.path.join(self.output_dir, output_filename)

        # === Step 1: Ensure json_input is a dictionary ===
        if isinstance(json_input, str):
            try:
                json_input = json.loads(json_input)
            except json.JSONDecodeError:
                print("❌ Error: json_input is a string but not valid JSON")
                raise ValueError("json_input must be a dictionary or valid JSON string")

        if not isinstance(json_input, dict):
            print(f"❌ Error: json_input is of type {type(json_input)}, expected dict")
            raise TypeError("json_input must be a dictionary")

        # === Step 2: Extract context values ===
        print(f"Received JSON input for PDF generation:")
        context_value = json_input.get('context', 'Report')
        print(f"Received JSON input for PDF generation: After extracting context value: {context_value}")

        print(f"Extracted context value: {context_value}, type: {type(context_value)}")

        print("RAW repr:", repr(context_value))
        print("TYPE:", type(context_value))
        print("IS STR:", isinstance(context_value, str))
        print("EQUAL CHECK:", context_value == "Campaign Performance Report")

        if isinstance(context_value, dict):
            print(f"Context value is a dict with keys: {list(context_value.keys())}")
            report_context = context_value.get('report_title', 'Report')
            short_title = context_value.get('short_title') or self.generate_acronym(report_context)
            date_range = context_value.get('date_range', '')
            
        elif isinstance(context_value, str):
            report_context = context_value
            print(f"Context value is a string: {report_context}")
            short_title = self.generate_acronym(context_value)
            date_range = ''
        else:
            report_context = 'Report'
            short_title = 'RPT'
            date_range = ''

        # === Step 3: Set up PDF document ===
        # doc = SimpleDocTemplate(
        #     output_path,
        #     pagesize=letter,
        #     leftMargin=self.margins["left"],
        #     rightMargin=self.margins["right"],
        #     topMargin=self.margins["top"],
        #     bottomMargin=self.margins["bottom"]
        # )
        from io import BytesIO
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=self.margins["left"],
            rightMargin=self.margins["right"],
            topMargin=self.margins["top"],
            bottomMargin=self.margins["bottom"]
        )

        # === Step 4: Load both logo images as BytesIO ===
        # Load Accenture logo
        accenture_logo_to_use = logo_path or self.logo_path
        accenture_logo_data = self._load_logo_as_bytesio(accenture_logo_to_use)
        
        # Load Cora logo
        cora_logo_to_use = cora_logo_path or self.cora_logo_path
        cora_logo_data = self._load_logo_as_bytesio(cora_logo_to_use)

        # === Step 5: Build PDF story content ===
        story = []
        for key, value in json_input.items():
            if key != 'context':
                self._process_section(story, key, value, level=1)

        # === Step 6: Generate PDF with header/footer and dual logos ===
        try:
            doc.build(
                story,
                onFirstPage=lambda canvas, doc: add_page_decor(
                    canvas, doc, self.brand_colors, self.page_width, self.page_height,
                    self.margins, self.header_footer_settings, 
                    accenture_logo_data=accenture_logo_data,
                    cora_logo_data=cora_logo_data,
                    context=report_context, 
                    short_title=short_title, 
                    date_range=date_range
                ),
                onLaterPages=lambda canvas, doc: add_page_decor(
                    canvas, doc, self.brand_colors, self.page_width, self.page_height,
                    self.margins, self.header_footer_settings,
                    accenture_logo_data=accenture_logo_data,
                    cora_logo_data=cora_logo_data,
                    context=report_context, 
                    short_title=short_title, 
                    date_range=date_range
                )
            )
            pdf_bytes = buffer.getvalue()
            buffer.close()
            print(f"bytes: {str(pdf_bytes)}")
            import gcsfs
            # gcs_pdf_path = f"gs://rmn-agentic/rmn_agent_engine_1/pdf2.pdf"
            fs = gcsfs.GCSFileSystem()
            with fs.open(gcs_pdf_path, "wb") as gcs_file:
                    gcs_file.write(pdf_bytes)
            print(f"PDF  saved to '{gcs_pdf_path}' successfully.")
            # print(f"✅ PDF generated successfully: {output_path}")
            return gcs_pdf_path
        except Exception as e:
            print(f"❌ Failed to generate PDF: {e}")
            import traceback
            traceback.print_exc()
            raise