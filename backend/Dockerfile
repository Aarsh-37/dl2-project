FROM python:3.11-slim
WORKDIR /code
# Optional: LaTeX toolchain so /resumes/export compiles the real template.
# Without it the endpoint falls back to the reportlab renderer (same order).
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     texlive-latex-base texlive-latex-recommended texlive-latex-extra \
#     && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
