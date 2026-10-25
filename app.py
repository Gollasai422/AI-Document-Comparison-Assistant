
import streamlit as st

from document_reader import read_pdf
from comparison import summarize_document, compare_documents
from report_generator import generate_comparison_report


st.set_page_config(
    page_title="AI Document Comparison Assistant",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background:
            radial-gradient(ellipse at top left, #172554 0%, transparent 38%),
            linear-gradient(135deg, #080d1b 0%, #10172a 55%, #111827 100%);
        color: #f8fafc;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #10182c, #080d19);
        border-right: 1px solid #26334d;
    }

    .hero {
        padding: 32px;
        border-radius: 24px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        background: linear-gradient(
            125deg,
            rgba(30, 64, 175, 0.35),
            rgba(15, 23, 42, 0.92)
        );
        margin-bottom: 26px;
        box-shadow: 0 15px 45px rgba(0, 0, 0, 0.2);
        animation: appear 0.7s ease-out;
    }

    .hero h1 {
        font-size: clamp(27px, 4vw, 42px);
        line-height: 1.2;
        font-weight: 800;
        margin: 0 0 12px 0;
        color: #f8fafc;
    }

    .hero p {
        color: #bdc9df;
        font-size: 15px;
        line-height: 1.8;
        margin: 0;
    }

    .eyebrow {
        color: #93c5fd;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 2px;
        margin-bottom: 12px;
    }

    .upload-card {
        border: 1px solid #334155;
        border-radius: 18px;
        padding: 18px;
        background: rgba(15, 23, 42, 0.72);
        min-height: 120px;
    }

    .upload-card h3 {
        color: #e2e8f0;
        font-size: 19px;
    }

    .upload-card p {
        color: #94a3b8;
        font-size: 13px;
    }

    .section-heading {
        color: #e2e8f0;
        font-size: 22px;
        font-weight: 700;
        margin: 22px 0 12px 0;
    }

    .metric-card {
        background: rgba(30, 41, 59, 0.75);
        border: 1px solid #334155;
        border-radius: 15px;
        padding: 18px;
        margin-bottom: 12px;
    }

    .metric-label {
        font-size: 12px;
        color: #94a3b8;
        margin-bottom: 6px;
    }

    .metric-value {
        color: #f8fafc;
        font-size: 22px;
        font-weight: 700;
        overflow-wrap: anywhere;
    }

    div.stButton > button,
    div.stDownloadButton > button {
        width: 100%;
        border-radius: 12px;
        min-height: 48px;
        border: 1px solid #60a5fa;
        background: linear-gradient(100deg, #2563eb, #7c3aed);
        color: white;
        font-weight: 700;
        transition: all 0.25s ease;
    }

    div.stButton > button:hover,
    div.stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(59, 130, 246, 0.35);
        border-color: #bfdbfe;
    }

    [data-testid="stFileUploader"] {
        border: 1px dashed #475569;
        border-radius: 14px;
        padding: 10px;
        background: rgba(15, 23, 42, 0.45);
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background: #1e293b;
        border-radius: 9px;
        padding: 10px 16px;
    }

    @keyframes appear {
        from {opacity: 0; transform: translateY(12px);}
        to {opacity: 1; transform: translateY(0);}
    }

    @media (max-width: 768px) {
        .hero { padding: 22px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def format_file_size(size_bytes):
    """Convert a file size in bytes into a readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def show_summary(summary, document):
    st.markdown("#### Summary")
    st.write(summary.get("summary", "No summary available."))

    st.markdown("#### Key points")
    key_points = summary.get("key_points", [])

    if key_points:
        for point in key_points:
            st.markdown(f"- {point}")
    else:
        st.info("No key points were returned.")

    details = summary.get("important_details", [])

    if details:
        st.markdown("#### Important details")
        for detail in details:
            if isinstance(detail, dict):
                text = detail.get("detail", str(detail))
                page = detail.get("page")
                if page:
                    st.markdown(f"- {text} — Page: {page}")
                else:
                    st.markdown(f"- {text}")
            else:
                st.markdown(f"- {detail}")

    limitations = summary.get("limitations", [])

    if limitations:
        st.markdown("#### Notes")
        for limitation in limitations:
            st.markdown(f"- {limitation}")


def show_comparison_items(items, empty_message):
    if not items:
        st.info(empty_message)
        return

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            st.write(item)
            continue

        topic = item.get("topic", f"Finding {index}")

        with st.container(border=True):
            st.markdown(f"**{topic}**")

            for key, value in item.items():
                if key == "topic":
                    continue

                label = key.replace("_", " ").capitalize()

                if isinstance(value, list):
                    value = ", ".join(str(part) for part in value)

                st.markdown(f"**{label}:** {value}")


if "comparison_results" not in st.session_state:
    st.session_state.comparison_results = None

if "summary_a" not in st.session_state:
    st.session_state.summary_a = None

if "summary_b" not in st.session_state:
    st.session_state.summary_b = None

if "document_a" not in st.session_state:
    st.session_state.document_a = None

if "document_b" not in st.session_state:
    st.session_state.document_b = None


with st.sidebar:
    st.markdown("## 📑 Document AI")
    st.caption("AI Document Comparison Assistant")
    st.divider()

    st.markdown("### How it works")
    st.markdown(
        """
        1. Upload two PDF documents.
        2. Review the extracted document details.
        3. Compare using Groq AI.
        4. Explore summaries and differences.
        5. Download the Word report.
        """
    )

    st.divider()
    st.caption("Supported input: text-based PDF files")
    st.caption("Keep your API key private.")

    if st.button("↻ Start a new comparison"):
        st.session_state.comparison_results = None
        st.session_state.summary_a = None
        st.session_state.summary_b = None
        st.session_state.document_a = None
        st.session_state.document_b = None
        st.rerun()


st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">DOCUMENT INTELLIGENCE PLATFORM</div>
        <h1>Compare documents.<br>Discover what matters.</h1>
        <p>
            Upload two PDF documents and let AI uncover their key points,
            similarities, differences, and important details in one place.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    '<div class="section-heading">01 &nbsp; Upload your documents</div>',
    unsafe_allow_html=True,
)

left, right = st.columns(2, gap="large")

with left:
    st.markdown(
        """
        <div class="upload-card">
            <h3>📘 Document A</h3>
            <p>Upload the first PDF for analysis.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    file_a = st.file_uploader(
        "Choose the first PDF",
        type=["pdf"],
        key="document_a_uploader",
    )

with right:
    st.markdown(
        """
        <div class="upload-card">
            <h3>📗 Document B</h3>
            <p>Upload the second PDF for comparison.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    file_b = st.file_uploader(
        "Choose the second PDF",
        type=["pdf"],
        key="document_b_uploader",
    )


document_a = None
document_b = None
upload_errors = []

if file_a is not None:
    try:
        document_a = read_pdf(file_a)
    except Exception as exc:
        upload_errors.append(f"Document A: {exc}")

if file_b is not None:
    try:
        document_b = read_pdf(file_b)
    except Exception as exc:
        upload_errors.append(f"Document B: {exc}")

for error in upload_errors:
    st.error(error)


if document_a and document_b:
    st.markdown(
        '<div class="section-heading">02 &nbsp; Document overview</div>',
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2, gap="large")

    with col_a:
        st.markdown("### 📘 Document A")
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">FILE NAME</div>
                <div class="metric-value">{document_a['filename']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.metric("Pages", document_a["page_count"])
        st.metric("File size", format_file_size(document_a["file_size"]))
        st.metric("Extracted characters", f"{document_a['character_count']:,}")

        with st.expander("Preview extracted text"):
            st.text(document_a["text"][:3000])

    with col_b:
        st.markdown("### 📗 Document B")
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">FILE NAME</div>
                <div class="metric-value">{document_b['filename']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.metric("Pages", document_b["page_count"])
        st.metric("File size", format_file_size(document_b["file_size"]))
        st.metric("Extracted characters", f"{document_b['character_count']:,}")

        with st.expander("Preview extracted text"):
            st.text(document_b["text"][:3000])


st.markdown(
    '<div class="section-heading">03 &nbsp; AI analysis</div>',
    unsafe_allow_html=True,
)

st.write(
    "Generate individual summaries and a side-by-side analysis of both PDFs."
)

if file_a is None or file_b is None:
    st.info("Upload both PDF documents to enable comparison.")

if st.button(
    "✨ Compare Documents with AI",
    type="primary",
    disabled=not (document_a and document_b),
):
    try:
        with st.spinner("Reading documents and generating summaries..."):
            summary_a = summarize_document(document_a, "Document A")
            summary_b = summarize_document(document_b, "Document B")

        with st.spinner("Analyzing similarities and differences..."):
            comparison_results = compare_documents(
                document_a,
                document_b,
            )

        st.session_state.document_a = document_a
        st.session_state.document_b = document_b
        st.session_state.summary_a = summary_a
        st.session_state.summary_b = summary_b
        st.session_state.comparison_results = comparison_results

        st.success("Document comparison completed successfully!")

    except Exception as exc:
        st.error(
            "The comparison could not be completed. "
            "Check your Groq API key, model availability, internet "
            "connection, and API usage limits."
        )
        with st.expander("Technical error details"):
            st.code(str(exc))


results = st.session_state.comparison_results

if results:
    summary_a = st.session_state.summary_a
    summary_b = st.session_state.summary_b
    document_a = st.session_state.document_a
    document_b = st.session_state.document_b

    st.markdown(
        '<div class="section-heading">04 &nbsp; Comparison results</div>',
        unsafe_allow_html=True,
    )

    st.markdown("### Overall comparison")
    st.write(results.get("overview", "No overview available."))

    tab_a, tab_b, tab_sim, tab_diff, tab_details, tab_conclusion = st.tabs(
        [
            "📘 Document A",
            "📗 Document B",
            "🤝 Similarities",
            "⚡ Differences",
            "🔎 Key details",
            "✅ Conclusion",
        ]
    )

    with tab_a:
        show_summary(summary_a, document_a)

    with tab_b:
        show_summary(summary_b, document_b)

    with tab_sim:
        show_comparison_items(
            results.get("similarities", []),
            "No similarities were identified.",
        )

    with tab_diff:
        show_comparison_items(
            results.get("differences", []),
            "No differences were identified.",
        )

    with tab_details:
        show_comparison_items(
            results.get("key_details", []),
            "No additional key details were identified.",
        )

    with tab_conclusion:
        st.write(results.get("conclusion", "No conclusion available."))

        limitations = results.get("limitations", [])

        if limitations:
            st.markdown("#### Limitations")
            for limitation in limitations:
                st.markdown(f"- {limitation}")

    st.markdown(
        '<div class="section-heading">05 &nbsp; Export your report</div>',
        unsafe_allow_html=True,
    )

    try:
        report_bytes = generate_comparison_report(
            document_a,
            document_b,
            summary_a,
            summary_b,
            results,
        )

        st.download_button(
            label="⬇ Download Comparison Report (.docx)",
            data=report_bytes,
            file_name="AI_Document_Comparison_Report.docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )

    except Exception as exc:
        st.error(f"Could not generate the Word report: {exc}")

    st.caption(
        "AI-generated findings may contain errors. "
        "Verify important information against the original PDFs."
    )


st.divider()
st.caption("AI Document Comparison Assistant · Built with Python, Streamlit and Groq")
