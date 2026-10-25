# 08 — Interview Evaluate (v1, temp 0.2, on-demand POST /mock/answer)

Score the candidate's answer against the ideal answer with a strict rubric. Scores 0–10 each. Be encouraging but honest; every weakness needs one concrete fix.

Question: {question}
Ideal answer: {ideal_answer}
Candidate answer: {answer}

Return JSON only: {"scores": {"technical_accuracy": int, "relevance": int, "completeness": int, "communication": int, "confidence": int}, "feedback": str, "fixes": []}
