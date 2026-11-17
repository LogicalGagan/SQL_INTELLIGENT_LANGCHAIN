"""Flask web server for SchemaScout.

- Shows the current database schema (tables, columns, primary/foreign keys).
- Provides a textarea for a natural‑language prompt.
- On submit it runs the full LangGraph pipeline (memory, ambiguity, generation, validation, repair, confidence, explanation).
- Returns the generated SQL, a brief explanation, confidence score and the query result as an HTML table.

Run with:
    python -m app.web
"""

from flask import Flask, render_template, request, redirect, url_for
from app.schema_loader import load_schema, SchemaInfo
from app.graph import app as graph_app  # compiled LangGraph workflow

app = Flask(__name__)

# Load schema once at startup
SCHEMA_INFO: SchemaInfo = load_schema()

def schema_to_html(schema_info: SchemaInfo) -> str:
    """Convert the schema info into a simple HTML representation.
    Returns a string that can be safely embedded in the template.
    """
    html_parts = []
    for tbl_name, tbl_meta in schema_info.tables.items():
        html_parts.append(f"<h3>{tbl_name}</h3>")
        html_parts.append("<ul>")
        for col in tbl_meta.columns:
            attrs = []
            if col.is_primary_key:
                attrs.append("PK")
            if col.is_foreign_key:
                attrs.append(f"FK → {col.foreign_key.table}.{col.foreign_key.column}")
            attr_str = f" ({', '.join(attrs)})" if attrs else ""
            html_parts.append(f"<li>{col.name}: {col.type}{attr_str}</li>")
        html_parts.append("</ul>")
    return "\n".join(html_parts)

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    sql = None
    explanation = None
    confidence = None
    confidence_reason = None
    error = None
    rows = []
    columns = []
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if question:
            # Run the LangGraph workflow – it expects a dict with a "question" key
            state = {"question": question}
            try:
                final_state = graph_app.invoke(state)
                sql = final_state.get("sql")
                explanation = final_state.get("explanation")
                confidence = final_state.get("confidence")
                confidence_reason = final_state.get("confidence_reason")
                error = final_state.get("error")
                # If validation succeeded, rows/columns will be present in final_state (we can reuse the executor output)
                if final_state.get("validation_ok"):
                    # The last dry‑run also executed the query (limited rows). We'll reuse those rows.
                    columns = final_state.get("dry_run_columns", [])
                    rows = final_state.get("dry_run_rows_data", [])
            except Exception as exc:
                error = str(exc)
    schema_html = schema_to_html(SCHEMA_INFO)
    return render_template(
        "index.html",
        schema_html=schema_html,
        result=result,
        sql=sql,
        explanation=explanation,
        confidence=confidence,
        confidence_reason=confidence_reason,
        error=error,
        columns=columns,
        rows=rows,
    )

if __name__ == "__main__":
    # Flask's built‑in server is sufficient for a demo; it runs on http://127.0.0.1:5000
    app.run(host="0.0.0.0", port=5000, debug=True)
