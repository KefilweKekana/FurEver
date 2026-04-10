// PDF Print Builder - Visual Drag & Drop Editor
// =============================================================================
frappe.ui.form.on("PDF Print Builder", {
    refresh(frm) {
        // ---------- toolbar buttons ----------
        frm.add_custom_button(__("Open Visual Builder"), () => frm.trigger("launch_builder"), __("Builder"));
        frm.add_custom_button(__("Generate Print Format"), () => {
            frappe.confirm(
                __("This will create/update the Frappe Print Format. Continue?"),
                () => {
                    frm.call("generate_print_format").then(r => {
                        if (r && r.message) {
                            frappe.show_alert({message: r.message.message, indicator: "green"});
                            frm.reload_doc();
                        }
                    });
                }
            );
        }, __("Builder"));
        frm.add_custom_button(__("Preview"), () => frm.trigger("preview_output"), __("Builder"));

        // Auto-launch builder if PDF file exists
        if (!frm.is_new() && frm.doc.pdf_file) {
            setTimeout(() => frm.trigger("launch_builder"), 500);
        }
    },

    source_doctype(frm) {
        if (frm.builder_instance) {
            frm.builder_instance.loadDoctypeFields();
        }
    },

    preview_output(frm) {
        if (!frm.doc.source_doctype) {
            frappe.msgprint(__("Please select a Source Doctype first."));
            return;
        }
        // Ask for a sample document to preview
        let d = new frappe.ui.Dialog({
            title: __("Preview Print Format"),
            fields: [
                {
                    fieldname: "sample_doc",
                    fieldtype: "Link",
                    label: __("Sample Document"),
                    options: frm.doc.source_doctype,
                    reqd: 1,
                },
            ],
            primary_action_label: __("Preview"),
            primary_action(values) {
                d.hide();
                let pf_name = frm.doc.print_format_name || frm.doc.title;
                window.open(
                    `/printview?doctype=${encodeURIComponent(frm.doc.source_doctype)}&name=${encodeURIComponent(values.sample_doc)}&format=${encodeURIComponent(pf_name)}`,
                    "_blank"
                );
            },
        });
        d.show();
    },

    launch_builder(frm) {
        if (!frm.doc.pdf_file) {
            frappe.msgprint(__("Please upload a PDF file first, then open the builder."));
            return;
        }
        if (!frm.fields_dict.builder_html) {
            frappe.msgprint(__("Builder HTML field not found. Please check the doctype setup."));
            return;
        }
        try {
            if (!frm.builder_instance) {
                frm.builder_instance = new PDFPrintBuilderEditor(frm);
            }
            frm.builder_instance.render();
        } catch (e) {
            console.error("PDF Builder launch error:", e);
            frappe.msgprint(__("Error launching Visual Builder: ") + e.message);
        }
    },
});


// =============================================================================
//  PDFPrintBuilderEditor – full visual drag/drop canvas
// =============================================================================
class PDFPrintBuilderEditor {
    constructor(frm) {
        this.frm = frm;
        this.currentPage = 1;
        this.zoom = 1;
        this.fields = []; // mirrors frm.doc.field_maps
        this.selectedField = null;
        this.doctypeFields = [];
        this.isDragging = false;
        this.isResizing = false;
        this.pdfImages = {}; // page_num -> data URL
        this.MM_TO_PX = 3.7795275591; // 1mm at 96dpi
    }

    render() {
        let root = this.frm.fields_dict.builder_html.$wrapper;
        root.empty();
        root.html(this.getEditorHTML());
        this.$root = root;
        this.$canvas = root.find(".pdfb-canvas");
        this.$sidebar = root.find(".pdfb-sidebar");
        this.$propPanel = root.find(".pdfb-properties");
        this.$fieldList = root.find(".pdfb-field-list");
        this.syncFieldsFromDoc();
        this.bindEvents();
        this.loadDoctypeFields();
        this.renderPDFBackground();
    }

    getEditorHTML() {
        return `
        <div class="pdfb-editor">
            <div class="pdfb-toolbar">
                <div class="pdfb-toolbar-left">
                    <button class="btn btn-xs btn-default pdfb-btn-zoom-out" title="Zoom Out">
                        <i class="fa fa-search-minus"></i>
                    </button>
                    <span class="pdfb-zoom-label">100%</span>
                    <button class="btn btn-xs btn-default pdfb-btn-zoom-in" title="Zoom In">
                        <i class="fa fa-search-plus"></i>
                    </button>
                    <button class="btn btn-xs btn-default pdfb-btn-zoom-fit" title="Fit to View">
                        <i class="fa fa-expand"></i>
                    </button>
                    <span class="pdfb-separator">|</span>
                    <button class="btn btn-xs btn-default pdfb-btn-prev-page" title="Previous Page">
                        <i class="fa fa-chevron-left"></i>
                    </button>
                    <span class="pdfb-page-label">Page 1 / 1</span>
                    <button class="btn btn-xs btn-default pdfb-btn-next-page" title="Next Page">
                        <i class="fa fa-chevron-right"></i>
                    </button>
                    <span class="pdfb-separator">|</span>
                    <button class="btn btn-xs btn-default pdfb-btn-toggle-bg" title="Toggle Background">
                        <i class="fa fa-eye"></i> BG
                    </button>
                    <button class="btn btn-xs btn-default pdfb-btn-grid" title="Toggle Grid">
                        <i class="fa fa-th"></i> Grid
                    </button>
                </div>
                <div class="pdfb-toolbar-right">
                    <button class="btn btn-xs btn-primary pdfb-btn-add-field">
                        <i class="fa fa-plus"></i> Add Field
                    </button>
                    <button class="btn btn-xs btn-warning pdfb-btn-save-fields">
                        <i class="fa fa-save"></i> Save Layout
                    </button>
                </div>
            </div>
            <div class="pdfb-body">
                <div class="pdfb-sidebar">
                    <div class="pdfb-sidebar-header">
                        <strong>Fields</strong>
                        <input type="text" class="form-control input-xs pdfb-field-search" placeholder="Search fields...">
                    </div>
                    <div class="pdfb-field-list"></div>
                    <div class="pdfb-doctype-fields">
                        <div class="pdfb-sidebar-header"><strong>Doctype Fields</strong></div>
                        <div class="pdfb-doctype-field-list"></div>
                    </div>
                </div>
                <div class="pdfb-canvas-wrapper">
                    <div class="pdfb-canvas">
                        <div class="pdfb-page-bg"></div>
                        <div class="pdfb-grid-overlay"></div>
                        <div class="pdfb-fields-container"></div>
                    </div>
                </div>
                <div class="pdfb-properties">
                    <div class="pdfb-prop-header"><strong>Properties</strong></div>
                    <div class="pdfb-prop-body">
                        <p class="text-muted">Select a field to edit its properties.</p>
                    </div>
                </div>
            </div>
        </div>`;
    }

    // ─── PDF RENDERING ──────────────────────────────────────
    renderPDFBackground() {
        let pdfUrl = this.frm.doc.pdf_file;
        if (!pdfUrl) return;

        // Use PDF.js (bundled with Frappe or loaded from CDN)
        let pdfjsLib = window.pdfjsLib || window["pdfjs-dist/build/pdf"];
        if (!pdfjsLib) {
            // Load PDF.js dynamically
            this.loadPDFJS().then(() => this.renderPDFBackground()).catch(err => {
                console.error("Failed to load PDF.js:", err);
                frappe.msgprint(__("Could not load the PDF viewer library. Please check your internet connection."));
            });
            return;
        }

        pdfjsLib.getDocument(pdfUrl).promise.then(pdf => {
            this.pdfDoc = pdf;
            let totalPages = pdf.numPages;
            this.frm.doc.total_pages = totalPages;
            this.$root.find(".pdfb-page-label").text(`Page ${this.currentPage} / ${totalPages}`);
            this.renderPage(this.currentPage);
        }).catch(err => {
            console.error("PDF load error:", err);
            frappe.msgprint(__("Could not load PDF. Make sure the file is a valid PDF."));
        });
    }

    loadPDFJS() {
        return new Promise((resolve, reject) => {
            if (window.pdfjsLib) { resolve(); return; }
            let script = document.createElement("script");
            script.src = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";
            script.onload = () => {
                // PDF.js 3.x CDN exposes as window.pdfjsLib directly
                let lib = window.pdfjsLib || window["pdfjs-dist/build/pdf"];
                if (lib) {
                    window.pdfjsLib = lib;
                    lib.GlobalWorkerOptions.workerSrc =
                        "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
                    resolve();
                } else {
                    reject(new Error("PDF.js loaded but global not found"));
                }
            };
            script.onerror = () => reject(new Error("Failed to load PDF.js from CDN"));
            document.head.appendChild(script);
        });
    }

    renderPage(pageNum) {
        if (!this.pdfDoc) return;
        this.pdfDoc.getPage(pageNum).then(page => {
            let viewport = page.getViewport({scale: 2}); // high-res render
            let canvas = document.createElement("canvas");
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            let ctx = canvas.getContext("2d");
            page.render({canvasContext: ctx, viewport: viewport}).promise.then(() => {
                let imgData = canvas.toDataURL("image/png");
                this.pdfImages[pageNum] = imgData;
                this.updateCanvasBackground(imgData);
            });
        });
    }

    updateCanvasBackground(imgData) {
        let w = (this.frm.doc.page_width_mm || 210) * this.MM_TO_PX * this.zoom;
        let h = (this.frm.doc.page_height_mm || 297) * this.MM_TO_PX * this.zoom;
        this.$canvas.css({width: w + "px", height: h + "px"});
        this.$canvas.find(".pdfb-page-bg").css({
            backgroundImage: `url(${imgData})`,
            backgroundSize: "100% 100%",
            width: "100%",
            height: "100%",
            position: "absolute",
            top: 0, left: 0,
        });
        this.renderFieldElements();
    }

    // ─── FIELD SYNC ─────────────────────────────────────────
    syncFieldsFromDoc() {
        this.fields = [];
        (this.frm.doc.field_maps || []).forEach((row, idx) => {
            this.fields.push({
                idx: row.idx,
                name: row.name,
                field_label: row.field_label || `Field ${idx + 1}`,
                field_type: row.field_type || "Doctype Field",
                doctype_fieldname: row.doctype_fieldname || "",
                child_doctype: row.child_doctype || "",
                child_fieldname: row.child_fieldname || "",
                static_value: row.static_value || "",
                page_number: row.page_number || 1,
                pos_x_mm: flt(row.pos_x_mm),
                pos_y_mm: flt(row.pos_y_mm),
                width_mm: flt(row.width_mm) || 40,
                height_mm: flt(row.height_mm) || 6,
                font_size: flt(row.font_size) || 10,
                font_family: row.font_family || "Arial",
                font_weight: row.font_weight || "normal",
                font_color: row.font_color || "#000000",
                text_align: row.text_align || "left",
                format_string: row.format_string || "",
                table_columns: row.table_columns || "",
                table_header_bg: row.table_header_bg || "#000000",
                table_header_color: row.table_header_color || "#FFFFFF",
                table_border_color: row.table_border_color || "#000000",
                table_font_size: flt(row.table_font_size) || 8,
                table_row_height_mm: flt(row.table_row_height_mm) || 6,
                table_max_rows: cint(row.table_max_rows) || 10,
                image_fit: row.image_fit || "contain",
                image_border_radius: flt(row.image_border_radius) || 0,
                border_width: flt(row.border_width) || 0,
                border_color: row.border_color || "#000000",
                background_color: row.background_color || "",
                opacity: row.opacity != null ? flt(row.opacity) : 1,
            });
        });
    }

    syncFieldsToDoc() {
        // Clear and rebuild the child table
        this.frm.doc.field_maps = [];
        this.fields.forEach((f, idx) => {
            let row = frappe.model.add_child(this.frm.doc, "PDF Print Field Map", "field_maps");
            Object.keys(f).forEach(k => {
                if (k !== "idx" && k !== "name") row[k] = f[k];
            });
        });
        this.frm.dirty();
        this.frm.refresh_fields();
    }

    // ─── RENDER FIELD ELEMENTS ON CANVAS ────────────────────
    renderFieldElements() {
        let container = this.$canvas.find(".pdfb-fields-container");
        container.empty();

        let pageFields = this.fields.filter(f => (f.page_number || 1) === this.currentPage);
        pageFields.forEach((f, idx) => {
            let el = this.createFieldElement(f, idx);
            container.append(el);
        });

        this.renderFieldList();
    }

    createFieldElement(f) {
        let z = this.zoom;
        let px = f.pos_x_mm * this.MM_TO_PX * z;
        let py = f.pos_y_mm * this.MM_TO_PX * z;
        let pw = f.width_mm * this.MM_TO_PX * z;
        let ph = f.height_mm ? f.height_mm * this.MM_TO_PX * z : "auto";

        let el = $(`<div class="pdfb-field-el" data-label="${frappe.utils.escape_html(f.field_label)}">
            <div class="pdfb-field-content">${frappe.utils.escape_html(f.field_label)}</div>
            <div class="pdfb-field-resize-handle"></div>
        </div>`);

        el.css({
            position: "absolute",
            left: px,
            top: py,
            width: pw,
            height: ph !== "auto" ? ph : "",
            minHeight: ph === "auto" ? "16px" : "",
            fontSize: (f.font_size || 10) * z + "pt",
            fontFamily: f.font_family || "Arial",
            fontWeight: f.font_weight || "normal",
            color: f.font_color || "#000",
            textAlign: f.text_align || "left",
            border: `1px dashed rgba(33,150,243,0.7)`,
            background: "rgba(33,150,243,0.08)",
            cursor: "move",
            zIndex: 10,
            padding: "1px 3px",
            boxSizing: "border-box",
            overflow: "hidden",
            lineHeight: "1.2",
            userSelect: "none",
        });

        if (f === this.selectedField) {
            el.css({border: "2px solid #2196F3", background: "rgba(33,150,243,0.18)"});
        }

        // Type badge
        let typeMap = {
            "Doctype Field": "DF",
            "Static Text": "ST",
            "Image Field": "IMG",
            "Table": "TBL",
            "Date Field": "DT",
            "Currency Field": "CUR",
            "Check Field": "CHK",
            "Signature": "SIG",
            "Barcode": "BAR",
            "QR Code": "QR",
        };
        let badge = typeMap[f.field_type] || "?";
        el.prepend(`<span class="pdfb-type-badge">${badge}</span>`);

        // Events
        el.on("mousedown", (e) => {
            if ($(e.target).hasClass("pdfb-field-resize-handle")) return;
            e.preventDefault();
            e.stopPropagation();
            this.selectField(f);
            this.startDrag(e, f, el);
        });

        el.find(".pdfb-field-resize-handle").on("mousedown", (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.selectField(f);
            this.startResize(e, f, el);
        });

        return el;
    }

    // ─── DRAG ───────────────────────────────────────────────
    startDrag(e, field, el) {
        this.isDragging = true;
        let startX = e.clientX, startY = e.clientY;
        let origX = field.pos_x_mm, origY = field.pos_y_mm;
        let z = this.zoom * this.MM_TO_PX;

        let move = (ev) => {
            let dx = (ev.clientX - startX) / z;
            let dy = (ev.clientY - startY) / z;
            field.pos_x_mm = Math.max(0, Math.round((origX + dx) * 10) / 10);
            field.pos_y_mm = Math.max(0, Math.round((origY + dy) * 10) / 10);
            el.css({left: field.pos_x_mm * this.MM_TO_PX * this.zoom, top: field.pos_y_mm * this.MM_TO_PX * this.zoom});
            this.updatePropValues(field);
        };
        let up = () => {
            $(document).off("mousemove", move).off("mouseup", up);
            this.isDragging = false;
        };
        $(document).on("mousemove", move).on("mouseup", up);
    }

    // ─── RESIZE ─────────────────────────────────────────────
    startResize(e, field, el) {
        this.isResizing = true;
        let startX = e.clientX, startY = e.clientY;
        let origW = field.width_mm, origH = field.height_mm || 6;
        let z = this.zoom * this.MM_TO_PX;

        let move = (ev) => {
            let dw = (ev.clientX - startX) / z;
            let dh = (ev.clientY - startY) / z;
            field.width_mm = Math.max(5, Math.round((origW + dw) * 10) / 10);
            field.height_mm = Math.max(3, Math.round((origH + dh) * 10) / 10);
            el.css({width: field.width_mm * this.MM_TO_PX * this.zoom, height: field.height_mm * this.MM_TO_PX * this.zoom});
            this.updatePropValues(field);
        };
        let up = () => {
            $(document).off("mousemove", move).off("mouseup", up);
            this.isResizing = false;
        };
        $(document).on("mousemove", move).on("mouseup", up);
    }

    // ─── SELECT / PROPERTIES ────────────────────────────────
    selectField(field) {
        this.selectedField = field;
        this.renderFieldElements(); // re-render to show selection
        this.renderPropertyPanel(field);
    }

    renderPropertyPanel(f) {
        let body = this.$propPanel.find(".pdfb-prop-body");
        body.empty();
        if (!f) {
            body.html('<p class="text-muted">Select a field to edit.</p>');
            return;
        }

        let html = `
        <div class="pdfb-prop-group">
            <label>Label</label>
            <input type="text" class="form-control input-sm pdfb-p" data-key="field_label" value="${frappe.utils.escape_html(f.field_label)}">
        </div>
        <div class="pdfb-prop-group">
            <label>Type</label>
            <select class="form-control input-sm pdfb-p" data-key="field_type">
                ${["Doctype Field","Static Text","Image Field","Table","Date Field","Currency Field","Check Field","Signature","Barcode","QR Code"].map(t =>
                    `<option ${t===f.field_type?'selected':''}>${t}</option>`
                ).join("")}
            </select>
        </div>
        <div class="pdfb-prop-group">
            <label>Fieldname</label>
            <input type="text" class="form-control input-sm pdfb-p" data-key="doctype_fieldname" value="${f.doctype_fieldname || ''}">
        </div>
        <div class="pdfb-prop-group">
            <label>Static Value</label>
            <textarea class="form-control input-sm pdfb-p" data-key="static_value" rows="2">${f.static_value || ''}</textarea>
        </div>
        <hr>
        <div class="pdfb-prop-row">
            <div class="pdfb-prop-group pdfb-half">
                <label>X (mm)</label>
                <input type="number" step="0.5" class="form-control input-sm pdfb-p" data-key="pos_x_mm" value="${f.pos_x_mm}">
            </div>
            <div class="pdfb-prop-group pdfb-half">
                <label>Y (mm)</label>
                <input type="number" step="0.5" class="form-control input-sm pdfb-p" data-key="pos_y_mm" value="${f.pos_y_mm}">
            </div>
        </div>
        <div class="pdfb-prop-row">
            <div class="pdfb-prop-group pdfb-half">
                <label>Width (mm)</label>
                <input type="number" step="0.5" class="form-control input-sm pdfb-p" data-key="width_mm" value="${f.width_mm}">
            </div>
            <div class="pdfb-prop-group pdfb-half">
                <label>Height (mm)</label>
                <input type="number" step="0.5" class="form-control input-sm pdfb-p" data-key="height_mm" value="${f.height_mm}">
            </div>
        </div>
        <div class="pdfb-prop-group">
            <label>Page #</label>
            <input type="number" min="1" class="form-control input-sm pdfb-p" data-key="page_number" value="${f.page_number || 1}">
        </div>
        <hr>
        <div class="pdfb-prop-row">
            <div class="pdfb-prop-group pdfb-half">
                <label>Font Size (pt)</label>
                <input type="number" step="0.5" class="form-control input-sm pdfb-p" data-key="font_size" value="${f.font_size || 10}">
            </div>
            <div class="pdfb-prop-group pdfb-half">
                <label>Weight</label>
                <select class="form-control input-sm pdfb-p" data-key="font_weight">
                    <option ${f.font_weight==='normal'?'selected':''}>normal</option>
                    <option ${f.font_weight==='bold'?'selected':''}>bold</option>
                </select>
            </div>
        </div>
        <div class="pdfb-prop-row">
            <div class="pdfb-prop-group pdfb-half">
                <label>Font</label>
                <select class="form-control input-sm pdfb-p" data-key="font_family">
                    ${["Arial","Helvetica","Times New Roman","Courier New","Verdana","Georgia"].map(ff =>
                        `<option ${ff===f.font_family?'selected':''}>${ff}</option>`
                    ).join("")}
                </select>
            </div>
            <div class="pdfb-prop-group pdfb-half">
                <label>Align</label>
                <select class="form-control input-sm pdfb-p" data-key="text_align">
                    ${["left","center","right"].map(a =>
                        `<option ${a===f.text_align?'selected':''}>${a}</option>`
                    ).join("")}
                </select>
            </div>
        </div>
        <div class="pdfb-prop-row">
            <div class="pdfb-prop-group pdfb-half">
                <label>Color</label>
                <input type="color" class="form-control input-sm pdfb-p pdfb-color" data-key="font_color" value="${f.font_color || '#000000'}">
            </div>
            <div class="pdfb-prop-group pdfb-half">
                <label>BG Color</label>
                <input type="color" class="form-control input-sm pdfb-p pdfb-color" data-key="background_color" value="${f.background_color || '#ffffff'}">
            </div>
        </div>
        <div class="pdfb-prop-group">
            <label>Format String</label>
            <input type="text" class="form-control input-sm pdfb-p" data-key="format_string" value="${f.format_string || ''}" placeholder="Date: dd-MM-yyyy | Currency: R {0:,.2f}">
        </div>
        <div class="pdfb-prop-row">
            <div class="pdfb-prop-group pdfb-half">
                <label>Border (px)</label>
                <input type="number" class="form-control input-sm pdfb-p" data-key="border_width" value="${f.border_width || 0}">
            </div>
            <div class="pdfb-prop-group pdfb-half">
                <label>Opacity</label>
                <input type="number" step="0.1" min="0" max="1" class="form-control input-sm pdfb-p" data-key="opacity" value="${f.opacity != null ? f.opacity : 1}">
            </div>
        </div>
        <hr>
        <div class="pdfb-prop-group" style="display:${f.field_type==='Table'?'block':'none'}">
            <label>Child Table Field</label>
            <input type="text" class="form-control input-sm pdfb-p" data-key="child_doctype" value="${f.child_doctype || ''}">
        </div>
        <div class="pdfb-prop-group" style="display:${f.field_type==='Table'?'block':'none'}">
            <label>Table Columns (JSON)</label>
            <textarea class="form-control input-sm pdfb-p" data-key="table_columns" rows="3">${f.table_columns || ''}</textarea>
        </div>
        <div class="pdfb-prop-group" style="display:${['Image Field','Signature'].includes(f.field_type)?'block':'none'}">
            <label>Image Fit</label>
            <select class="form-control input-sm pdfb-p" data-key="image_fit">
                ${["contain","cover","fill","none"].map(v =>
                    `<option ${v===f.image_fit?'selected':''}>${v}</option>`
                ).join("")}
            </select>
        </div>
        <hr>
        <button class="btn btn-xs btn-default pdfb-btn-duplicate"><i class="fa fa-copy"></i> Duplicate</button>
        <button class="btn btn-xs btn-danger pdfb-btn-delete"><i class="fa fa-trash"></i> Delete</button>
        `;

        body.html(html);

        // Bind property changes
        body.find(".pdfb-p").on("change input", (e) => {
            let key = $(e.target).data("key");
            let val = $(e.target).val();
            // Convert numeric fields
            let numericKeys = ["pos_x_mm","pos_y_mm","width_mm","height_mm","font_size","page_number","border_width","opacity","table_font_size","table_row_height_mm","table_max_rows","image_border_radius"];
            if (numericKeys.includes(key)) val = parseFloat(val) || 0;
            f[key] = val;
            this.renderFieldElements();
        });

        body.find(".pdfb-btn-duplicate").on("click", () => this.duplicateField(f));
        body.find(".pdfb-btn-delete").on("click", () => this.deleteField(f));
    }

    updatePropValues(f) {
        if (this.selectedField !== f) return;
        this.$propPanel.find('[data-key="pos_x_mm"]').val(f.pos_x_mm);
        this.$propPanel.find('[data-key="pos_y_mm"]').val(f.pos_y_mm);
        this.$propPanel.find('[data-key="width_mm"]').val(f.width_mm);
        this.$propPanel.find('[data-key="height_mm"]').val(f.height_mm);
    }

    // ─── FIELD LIST SIDEBAR ─────────────────────────────────
    renderFieldList() {
        let list = this.$fieldList;
        list.empty();
        this.fields.forEach((f) => {
            let active = f === this.selectedField ? "pdfb-fl-active" : "";
            let item = $(`<div class="pdfb-fl-item ${active}">
                <span class="pdfb-fl-badge">${f.page_number || 1}</span>
                <span class="pdfb-fl-label">${frappe.utils.escape_html(f.field_label)}</span>
                <span class="pdfb-fl-type">${f.field_type}</span>
            </div>`);
            item.on("click", () => {
                if ((f.page_number || 1) !== this.currentPage) {
                    this.currentPage = f.page_number || 1;
                    this.renderPage(this.currentPage);
                    this.$root.find(".pdfb-page-label").text(`Page ${this.currentPage} / ${this.frm.doc.total_pages || 1}`);
                }
                this.selectField(f);
            });
            list.append(item);
        });
    }

    // ─── DOCTYPE FIELDS SIDEBAR ─────────────────────────────
    loadDoctypeFields() {
        if (!this.frm.doc.source_doctype) return;
        this.frm.call("get_doctype_fields").then(r => {
            this.doctypeFields = r.message || [];
            this.renderDoctypeFieldList();
        });
    }

    renderDoctypeFieldList() {
        let list = this.$root.find(".pdfb-doctype-field-list");
        list.empty();
        this.doctypeFields.forEach(f => {
            let item = $(`<div class="pdfb-df-item" draggable="true" title="${f.fieldtype}: ${f.fieldname}">
                <span class="pdfb-df-label">${frappe.utils.escape_html(f.label)}</span>
                <span class="pdfb-df-type">${f.fieldtype}</span>
            </div>`);

            // Double-click to add
            item.on("dblclick", () => {
                this.addFieldFromDoctype(f);
            });

            // Drag start
            item.on("dragstart", (e) => {
                e.originalEvent.dataTransfer.setData("text/plain", JSON.stringify(f));
                e.originalEvent.dataTransfer.effectAllowed = "copy";
            });

            list.append(item);
        });
    }

    addFieldFromDoctype(df) {
        let typeMap = {
            "Date": "Date Field",
            "Currency": "Currency Field",
            "Check": "Check Field",
            "Attach Image": "Image Field",
            "Attach": "Image Field",
            "Signature": "Signature",
            "Table": "Table",
        };

        let f = {
            field_label: df.label,
            field_type: typeMap[df.fieldtype] || "Doctype Field",
            doctype_fieldname: df.fieldname,
            page_number: this.currentPage,
            pos_x_mm: 20,
            pos_y_mm: 20 + this.fields.filter(x => (x.page_number || 1) === this.currentPage).length * 8,
            width_mm: df.fieldtype === "Table" ? 170 : 50,
            height_mm: df.fieldtype === "Table" ? 40 : 6,
            font_size: 10,
            font_family: "Arial",
            font_weight: "normal",
            font_color: "#000000",
            text_align: "left",
            format_string: "",
            static_value: "",
            child_doctype: "",
            child_fieldname: "",
            table_columns: "",
            table_header_bg: "#000000",
            table_header_color: "#FFFFFF",
            table_border_color: "#000000",
            table_font_size: 8,
            table_row_height_mm: 6,
            table_max_rows: 10,
            image_fit: "contain",
            image_border_radius: 0,
            border_width: 0,
            border_color: "#000000",
            background_color: "",
            opacity: 1,
        };

        // Auto-set table config
        if (df.fieldtype === "Table" && df.child_fields) {
            f.child_doctype = df.fieldname;
            let cols = df.child_fields.slice(0, 8).map(cf => ({
                field: cf.fieldname,
                label: cf.label,
                width: Math.round(100 / Math.min(df.child_fields.length, 8)),
            }));
            f.table_columns = JSON.stringify(cols);
            f.child_fieldname = df.child_fields.map(cf => cf.fieldname).join(",");
        }

        this.fields.push(f);
        this.renderFieldElements();
        this.selectField(f);
    }

    // ─── ADD / DELETE / DUPLICATE ────────────────────────────
    addField() {
        let f = {
            field_label: "New Field",
            field_type: "Doctype Field",
            doctype_fieldname: "",
            page_number: this.currentPage,
            pos_x_mm: 30,
            pos_y_mm: 30 + this.fields.filter(x => (x.page_number || 1) === this.currentPage).length * 8,
            width_mm: 50,
            height_mm: 6,
            font_size: 10,
            font_family: "Arial",
            font_weight: "normal",
            font_color: "#000000",
            text_align: "left",
            format_string: "",
            static_value: "",
            child_doctype: "",
            child_fieldname: "",
            table_columns: "",
            table_header_bg: "#000000",
            table_header_color: "#FFFFFF",
            table_border_color: "#000000",
            table_font_size: 8,
            table_row_height_mm: 6,
            table_max_rows: 10,
            image_fit: "contain",
            image_border_radius: 0,
            border_width: 0,
            border_color: "#000000",
            background_color: "",
            opacity: 1,
        };
        this.fields.push(f);
        this.renderFieldElements();
        this.selectField(f);
    }

    duplicateField(f) {
        let copy = Object.assign({}, f);
        copy.field_label = f.field_label + " (copy)";
        copy.pos_x_mm = f.pos_x_mm + 5;
        copy.pos_y_mm = f.pos_y_mm + 5;
        delete copy.name;
        this.fields.push(copy);
        this.renderFieldElements();
        this.selectField(copy);
    }

    deleteField(f) {
        this.fields = this.fields.filter(x => x !== f);
        this.selectedField = null;
        this.renderFieldElements();
        this.renderPropertyPanel(null);
    }

    // ─── EVENT BINDING ──────────────────────────────────────
    bindEvents() {
        let root = this.$root;

        // Zoom
        root.find(".pdfb-btn-zoom-in").on("click", () => this.setZoom(this.zoom + 0.1));
        root.find(".pdfb-btn-zoom-out").on("click", () => this.setZoom(this.zoom - 0.1));
        root.find(".pdfb-btn-zoom-fit").on("click", () => {
            let wrapperW = root.find(".pdfb-canvas-wrapper").width();
            let canvasW = (this.frm.doc.page_width_mm || 210) * this.MM_TO_PX;
            this.setZoom(Math.min((wrapperW - 40) / canvasW, 1.5));
        });

        // Page nav
        root.find(".pdfb-btn-prev-page").on("click", () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.renderPage(this.currentPage);
                root.find(".pdfb-page-label").text(`Page ${this.currentPage} / ${this.frm.doc.total_pages || 1}`);
                this.renderFieldElements();
            }
        });
        root.find(".pdfb-btn-next-page").on("click", () => {
            let total = this.frm.doc.total_pages || 1;
            if (this.currentPage < total) {
                this.currentPage++;
                this.renderPage(this.currentPage);
                root.find(".pdfb-page-label").text(`Page ${this.currentPage} / ${total}`);
                this.renderFieldElements();
            }
        });

        // Toggle background
        let bgVisible = true;
        root.find(".pdfb-btn-toggle-bg").on("click", () => {
            bgVisible = !bgVisible;
            this.$canvas.find(".pdfb-page-bg").toggle(bgVisible);
        });

        // Toggle grid
        let gridVisible = false;
        root.find(".pdfb-btn-grid").on("click", () => {
            gridVisible = !gridVisible;
            let overlay = this.$canvas.find(".pdfb-grid-overlay");
            if (gridVisible) {
                let w = (this.frm.doc.page_width_mm || 210) * this.MM_TO_PX * this.zoom;
                let h = (this.frm.doc.page_height_mm || 297) * this.MM_TO_PX * this.zoom;
                let gridSize = 10 * this.MM_TO_PX * this.zoom; // 10mm grid
                overlay.css({
                    position: "absolute", top: 0, left: 0,
                    width: w, height: h, zIndex: 5, pointerEvents: "none",
                    backgroundImage: `repeating-linear-gradient(0deg, rgba(0,0,0,0.08) 0px, transparent 1px, transparent ${gridSize}px),
                                      repeating-linear-gradient(90deg, rgba(0,0,0,0.08) 0px, transparent 1px, transparent ${gridSize}px)`,
                    backgroundSize: `${gridSize}px ${gridSize}px`,
                }).show();
            } else {
                overlay.hide();
            }
        });

        // Add field button
        root.find(".pdfb-btn-add-field").on("click", () => this.addField());

        // Save
        root.find(".pdfb-btn-save-fields").on("click", () => {
            this.syncFieldsToDoc();
            this.frm.save().then(() => {
                frappe.show_alert({message: __("Layout saved!"), indicator: "green"});
            });
        });

        // Click blank canvas to deselect
        this.$canvas.on("click", (e) => {
            if ($(e.target).closest(".pdfb-field-el").length === 0) {
                this.selectedField = null;
                this.renderFieldElements();
                this.renderPropertyPanel(null);
            }
        });

        // Canvas drop from sidebar
        this.$canvas.on("dragover", (e) => { e.preventDefault(); });
        this.$canvas.on("drop", (e) => {
            e.preventDefault();
            let data = e.originalEvent.dataTransfer.getData("text/plain");
            try {
                let df = JSON.parse(data);
                let rect = this.$canvas[0].getBoundingClientRect();
                let dropX = (e.originalEvent.clientX - rect.left) / (this.MM_TO_PX * this.zoom);
                let dropY = (e.originalEvent.clientY - rect.top) / (this.MM_TO_PX * this.zoom);
                df._dropX = Math.round(dropX * 10) / 10;
                df._dropY = Math.round(dropY * 10) / 10;
                this.addFieldFromDoctypeDrop(df);
            } catch(ex) { /* ignore invalid drops */ }
        });

        // Search
        root.find(".pdfb-field-search").on("input", (e) => {
            let q = $(e.target).val().toLowerCase();
            root.find(".pdfb-fl-item").each(function() {
                let label = $(this).find(".pdfb-fl-label").text().toLowerCase();
                $(this).toggle(label.includes(q));
            });
        });

        // Keyboard shortcuts
        $(document).off("keydown.pdfbuilder").on("keydown.pdfbuilder", (e) => {
            if (!this.selectedField) return;
            let step = e.shiftKey ? 1 : 0.5;
            if (e.key === "Delete" || e.key === "Backspace") {
                if (!$(e.target).is("input, textarea, select")) {
                    e.preventDefault();
                    this.deleteField(this.selectedField);
                }
            }
            if (e.key === "ArrowLeft") { e.preventDefault(); this.selectedField.pos_x_mm = Math.max(0, this.selectedField.pos_x_mm - step); this.renderFieldElements(); this.updatePropValues(this.selectedField); }
            if (e.key === "ArrowRight") { e.preventDefault(); this.selectedField.pos_x_mm += step; this.renderFieldElements(); this.updatePropValues(this.selectedField); }
            if (e.key === "ArrowUp") { e.preventDefault(); this.selectedField.pos_y_mm = Math.max(0, this.selectedField.pos_y_mm - step); this.renderFieldElements(); this.updatePropValues(this.selectedField); }
            if (e.key === "ArrowDown") { e.preventDefault(); this.selectedField.pos_y_mm += step; this.renderFieldElements(); this.updatePropValues(this.selectedField); }
        });
    }

    addFieldFromDoctypeDrop(df) {
        let f = {
            field_label: df.label,
            field_type: this.mapFieldtype(df.fieldtype),
            doctype_fieldname: df.fieldname,
            page_number: this.currentPage,
            pos_x_mm: df._dropX || 20,
            pos_y_mm: df._dropY || 20,
            width_mm: df.fieldtype === "Table" ? 170 : 50,
            height_mm: df.fieldtype === "Table" ? 40 : 6,
            font_size: 10, font_family: "Arial", font_weight: "normal",
            font_color: "#000000", text_align: "left", format_string: "",
            static_value: "", child_doctype: "", child_fieldname: "",
            table_columns: "", table_header_bg: "#000000", table_header_color: "#FFFFFF",
            table_border_color: "#000000", table_font_size: 8, table_row_height_mm: 6,
            table_max_rows: 10, image_fit: "contain", image_border_radius: 0,
            border_width: 0, border_color: "#000000", background_color: "", opacity: 1,
        };
        this.fields.push(f);
        this.renderFieldElements();
        this.selectField(f);
    }

    mapFieldtype(ft) {
        return {"Date":"Date Field","Currency":"Currency Field","Check":"Check Field",
                "Attach Image":"Image Field","Attach":"Image Field","Signature":"Signature",
                "Table":"Table"}[ft] || "Doctype Field";
    }

    setZoom(z) {
        this.zoom = Math.max(0.3, Math.min(z, 3));
        this.$root.find(".pdfb-zoom-label").text(Math.round(this.zoom * 100) + "%");
        if (this.pdfImages[this.currentPage]) {
            this.updateCanvasBackground(this.pdfImages[this.currentPage]);
        }
    }
}
