
@app.route("/download-reviews")
def download_reviews():
    import csv
    import io
    import json

    log_path = "prompts/gpt_review_log.json"
    input_path = "prompts/learning_log.json"

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            reviews = json.load(f)
        with open(input_path, "r", encoding="utf-8") as f:
            inputs = json.load(f)
    except:
        reviews = {}
        inputs = {}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["entry_id", "input", "gpt_response", "empathy", "escalation", "diagnosis", "clarity", "comments"])

    for entry_id, review in reviews.items():
        input_text = inputs.get(entry_id, {}).get("input", "")
        gpt_response = inputs.get(entry_id, {}).get("gpt_response", "")
        writer.writerow([
            entry_id,
            input_text,
            gpt_response,
            review.get("empathy", ""),
            review.get("escalation", ""),
            review.get("diagnosis", ""),
            review.get("clarity", ""),
            review.get("comments", "")
        ])

    output.seek(0)
    return app.response_class(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=gpt_review_log.csv"}
    )
