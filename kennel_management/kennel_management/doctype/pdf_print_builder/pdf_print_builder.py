import frappe
import json
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class PDFPrintBuilder(Document):
    def validate(self):
        if not self.print_format_name:
            self.print_format_name = self.title

    def on_update(self):
        self.generated_html = self.build_print_format_html()
        # update without triggering another on_update
        frappe.db.set_value("PDF Print Builder", self.name, "generated_html", self.generated_html, update_modified=False)

    def build_print_format_html(self):
        """Generate the full Jinja HTML that acts as a Frappe Print Format."""
        pages = {}
        for fm in self.field_maps:
            pg = cint(fm.page_number) or 1
            pages.setdefault(pg, []).append(fm)

        total_pages = max(cint(self.total_pages), max(pages.keys()) if pages else 1)
        w = flt(self.page_width_mm) or 210
        h = flt(self.page_height_mm) or 297
        margin = flt(self.page_margin_mm) or 0

        lines = []
        lines.append(self._build_style(w, h, margin, total_pages))
        lines.append('<div class="pdf-overlay-print">')

        for pg_num in range(1, total_pages + 1):
            lines.append(f'  <div class="pdf-page" data-page="{pg_num}">')
            lines.append(f'    <div class="pdf-bg-layer">')
            lines.append(f'      <img src="{{{{ pdf_page_image({pg_num}) }}}}" class="pdf-bg-img" />')
            lines.append(f'    </div>')
            lines.append(f'    <div class="pdf-fields-layer">')

            for fm in pages.get(pg_num, []):
                lines.append(self._build_field_element(fm))

            lines.append(f'    </div>')
            lines.append(f'  </div>')

            if pg_num < total_pages:
                lines.append('  <div class="page-break"></div>')

        lines.append('</div>')

        # Add the Jinja macro for pdf_page_image
        jinja_header = self._build_jinja_macros()

        return jinja_header + "\n" + "\n".join(lines)

    def _build_style(self, w, h, margin, total_pages):
        return f"""<style>
@page {{
    size: {w}mm {h}mm;
    margin: {margin}mm;
}}
@media print {{
    body {{ margin: 0; padding: 0; }}
    .print-format {{ padding: 0 !important; margin: 0 !important; }}
}}
.pdf-overlay-print {{
    font-family: Arial, Helvetica, sans-serif;
    color: #000;
}}
.pdf-page {{
    position: relative;
    width: {w}mm;
    height: {h}mm;
    overflow: hidden;
    page-break-after: always;
    page-break-inside: avoid;
}}
.pdf-page:last-child {{
    page-break-after: auto;
}}
.pdf-bg-layer {{
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: 0;
}}
.pdf-bg-img {{
    width: 100%;
    height: 100%;
    object-fit: fill;
}}
.pdf-fields-layer {{
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: 1;
}}
.pdf-field {{
    position: absolute;
    overflow: hidden;
    box-sizing: border-box;
    line-height: 1.2;
}}
.pdf-field-table {{
    border-collapse: collapse;
    width: 100%;
}}
.pdf-field-table th {{
    text-align: left;
    padding: 1mm 1.5mm;
    font-size: 8pt;
}}
.pdf-field-table td {{
    padding: 0.8mm 1.5mm;
    vertical-align: top;
}}
.pdf-field-img {{
    max-width: 100%;
    max-height: 100%;
    display: block;
}}
.pdf-check-mark {{
    font-weight: bold;
}}
.page-break {{
    page-break-before: always;
    height: 0; margin: 0; padding: 0;
}}
</style>"""

    def _build_jinja_macros(self):
        """Build the Jinja macros for PDF background image resolution.

        For wkhtmltopdf printing, we convert PDF pages to images server-side.
        The macro calls our API to get pre-rendered page images.
        Falls back to showing the PDF URL directly (works for single-page PDFs
        converted to images via the builder).
        """
        pdf_url = self.pdf_file or ""
        builder_name = self.name or ""
        return f"""{{% macro pdf_page_image(page_num) %}}/api/method/kennel_management.api.get_pdf_page_image?builder={builder_name}&page={{{{ page_num }}}}{{% endmacro %}}"""

    def _build_field_element(self, fm):
        """Build a single positioned HTML element for a field map entry."""
        x = flt(fm.pos_x_mm)
        y = flt(fm.pos_y_mm)
        w = flt(fm.width_mm) or 40
        h = flt(fm.height_mm)
        fs = flt(fm.font_size) or 10
        fw = fm.font_weight or "normal"
        ff = fm.font_family or "Arial"
        fc = fm.font_color or "#000000"
        ta = fm.text_align or "left"
        op = flt(fm.opacity) if fm.opacity else 1
        bw = flt(fm.border_width)
        bc = fm.border_color or "#000000"
        bg = fm.background_color or ""

        style_parts = [
            f"left:{x}mm",
            f"top:{y}mm",
            f"width:{w}mm",
            f"font-size:{fs}pt",
            f"font-family:{ff},sans-serif",
            f"font-weight:{fw}",
            f"color:{fc}",
            f"text-align:{ta}",
        ]
        if h:
            style_parts.append(f"height:{h}mm")
        if op < 1:
            style_parts.append(f"opacity:{op}")
        if bw:
            style_parts.append(f"border:{bw}px solid {bc}")
        if bg:
            style_parts.append(f"background:{bg}")

        style = ";".join(style_parts)
        field_type = fm.field_type or "Doctype Field"
        field_name = fm.doctype_fieldname or ""
        fmt = fm.format_string or ""

        if field_type == "Static Text":
            content = fm.static_value or ""
            # support jinja inside static value
            return f'      <div class="pdf-field" style="{style}">{content}</div>'

        elif field_type == "Check Field":
            check_true = "✓"
            check_false = "✗"
            if fmt:
                parts = fmt.split("/")
                check_true = parts[0] if len(parts) > 0 else "✓"
                check_false = parts[1] if len(parts) > 1 else "✗"
            return (f'      <div class="pdf-field pdf-check-mark" style="{style}">'
                    f'{{% if doc.{field_name} %}}{check_true}{{% else %}}{check_false}{{% endif %}}'
                    f'</div>')

        elif field_type == "Date Field":
            date_fmt = fmt or "dd-MM-yyyy"
            return (f'      <div class="pdf-field" style="{style}">'
                    f'{{{{ frappe.utils.formatdate(doc.{field_name}, "{date_fmt}") if doc.{field_name} else "" }}}}'
                    f'</div>')

        elif field_type == "Currency Field":
            if fmt:
                return (f'      <div class="pdf-field" style="{style}">'
                        f'{{% if doc.{field_name} %}}{{{{ "{fmt}".format(doc.{field_name}) }}}}{{% endif %}}'
                        f'</div>')
            else:
                return (f'      <div class="pdf-field" style="{style}">'
                        f'{{{{ frappe.utils.fmt_money(doc.{field_name}) if doc.{field_name} else "" }}}}'
                        f'</div>')

        elif field_type == "Image Field":
            fit = fm.image_fit or "contain"
            radius = flt(fm.image_border_radius)
            img_style = f"object-fit:{fit}"
            if radius:
                img_style += f";border-radius:{radius}mm"
            return (f'      <div class="pdf-field" style="{style}">'
                    f'{{% if doc.{field_name} %}}'
                    f'<img src="{{{{ doc.{field_name} }}}}" class="pdf-field-img" style="{img_style}" />'
                    f'{{% endif %}}'
                    f'</div>')

        elif field_type == "Signature":
            fit = fm.image_fit or "contain"
            return (f'      <div class="pdf-field" style="{style}">'
                    f'{{% if doc.{field_name} %}}'
                    f'<img src="{{{{ doc.{field_name} }}}}" class="pdf-field-img" style="object-fit:{fit}" />'
                    f'{{% endif %}}'
                    f'</div>')

        elif field_type == "Barcode":
            return (f'      <div class="pdf-field" style="{style}">'
                    f'{{% if doc.{field_name} %}}'
                    f'<svg class="pdf-barcode" data-value="{{{{ doc.{field_name} }}}}"></svg>'
                    f'{{% endif %}}'
                    f'</div>')

        elif field_type == "QR Code":
            return (f'      <div class="pdf-field" style="{style}">'
                    f'{{% if doc.{field_name} %}}'
                    f'<img src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={{{{ doc.{field_name} | urlencode }}}}" '
                    f'class="pdf-field-img" style="object-fit:contain" />'
                    f'{{% endif %}}'
                    f'</div>')

        elif field_type == "Table":
            return self._build_table_element(fm, style)

        else:
            # Default: Doctype Field - just print the value
            return f'      <div class="pdf-field" style="{style}">{{{{ doc.{field_name} or "" }}}}</div>'

    def _build_table_element(self, fm, style):
        """Build an HTML table for child table fields."""
        child_table_field = fm.child_doctype or ""
        columns_json = fm.table_columns or "[]"
        try:
            columns = json.loads(columns_json)
        except (json.JSONDecodeError, TypeError):
            columns = []

        # Fallback: use child_fieldname comma-separated list
        if not columns and fm.child_fieldname:
            fields = [f.strip() for f in fm.child_fieldname.split(",")]
            columns = [{"field": f, "label": f.replace("_", " ").title(), "width": round(100 / len(fields))} for f in fields]

        if not columns:
            return f'      <div class="pdf-field" style="{style}"><!-- No columns configured --></div>'

        hdr_bg = fm.table_header_bg or "#000000"
        hdr_color = fm.table_header_color or "#FFFFFF"
        bdr_color = fm.table_border_color or "#000000"
        tfs = flt(fm.table_font_size) or 8
        rh = flt(fm.table_row_height_mm) or 6
        max_rows = cint(fm.table_max_rows) or 10

        lines = [f'      <div class="pdf-field" style="{style}">']
        lines.append(f'        <table class="pdf-field-table" style="font-size:{tfs}pt;border:1px solid {bdr_color};">')

        # Header
        lines.append("          <thead><tr>")
        for col in columns:
            w = col.get("width", "")
            w_style = f'width:{w}%' if w else ''
            lines.append(f'            <th style="background:{hdr_bg};color:{hdr_color};border:1px solid {bdr_color};{w_style}">{col.get("label", col.get("field", ""))}</th>')
        lines.append("          </tr></thead>")

        # Body
        lines.append("          <tbody>")
        lines.append(f'          {{% for row in doc.{child_table_field}[:{ max_rows}] %}}')
        lines.append(f'            <tr style="height:{rh}mm">')
        for col in columns:
            field = col.get("field", "")
            lines.append(f'              <td style="border:1px solid {bdr_color}">{{{{ row.{field} or "" }}}}</td>')
        lines.append("            </tr>")
        lines.append("          {% endfor %}")

        # Empty rows to fill
        lines.append(f'          {{% for i in range(doc.{child_table_field} | length, {max_rows}) %}}')
        lines.append(f'            <tr style="height:{rh}mm">')
        for _ in columns:
            lines.append(f'              <td style="border:1px solid {bdr_color}">&nbsp;</td>')
        lines.append("            </tr>")
        lines.append("          {% endfor %}")

        lines.append("          </tbody>")
        lines.append("        </table>")
        lines.append("      </div>")

        return "\n".join(lines)

    @frappe.whitelist()
    def generate_print_format(self):
        """Build the HTML and create/update the actual Frappe Print Format document."""
        self.generated_html = self.build_print_format_html()
        frappe.db.set_value("PDF Print Builder", self.name, "generated_html", self.generated_html, update_modified=False)

        pf_name = self.print_format_name or self.title

        if frappe.db.exists("Print Format", pf_name):
            pf = frappe.get_doc("Print Format", pf_name)
            pf.html = self.generated_html
            pf.save(ignore_permissions=True)
        else:
            pf = frappe.get_doc({
                "doctype": "Print Format",
                "name": pf_name,
                "doc_type": self.source_doctype,
                "module": "Kennel Management",
                "print_format_type": "Jinja",
                "standard": "No",
                "custom_format": 1,
                "print_format_builder": 0,
                "html": self.generated_html,
            })
            pf.insert(ignore_permissions=True)

        self.status = "Published"
        frappe.db.set_value("PDF Print Builder", self.name, "status", "Published", update_modified=False)

        return {"print_format": pf.name, "message": _("Print Format '{}' generated successfully.").format(pf.name)}

    @frappe.whitelist()
    def get_doctype_fields(self):
        """Return all fields from the source doctype for the field picker."""
        if not self.source_doctype:
            return []

        meta = frappe.get_meta(self.source_doctype)
        fields = []
        for f in meta.fields:
            if f.fieldtype in ("Section Break", "Column Break", "Tab Break"):
                continue
            entry = {
                "fieldname": f.fieldname,
                "label": f.label or f.fieldname,
                "fieldtype": f.fieldtype,
                "options": f.options or "",
            }
            # If it's a table field, fetch child fields too
            if f.fieldtype == "Table" and f.options:
                try:
                    child_meta = frappe.get_meta(f.options)
                    entry["child_fields"] = [
                        {"fieldname": cf.fieldname, "label": cf.label or cf.fieldname, "fieldtype": cf.fieldtype}
                        for cf in child_meta.fields
                        if cf.fieldtype not in ("Section Break", "Column Break", "Tab Break")
                    ]
                except Exception:
                    entry["child_fields"] = []
            fields.append(entry)
        return fields
