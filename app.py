from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from models import SurveySubmission, StoredSurveyRecord
from storage import append_json_line
from hashlib import sha256

app = Flask(__name__)
# Allow cross-origin requests so the static HTML can POST from localhost or file://
CORS(app, resources={r"/v1/*": {"origins": "*"}})

@app.route("/ping", methods=["GET"])
def ping():
    """Simple health check endpoint."""
    return jsonify({
        "status": "ok",
        "message": "API is alive",
        "utc_time": datetime.now(timezone.utc).isoformat()
    })

@app.post("/v1/survey")
def submit_survey():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        record = SurveySubmission(**payload)
    except ValidationError as e:
        return jsonify({"error": "Validation error", "details": e.errors()}), 422

    # Create a dictionary from the pydantic model to modify before saving
    record_dict = record.dict()

    # Hash PII fields
    record_dict["email"] = sha256(record.email.encode()).hexdigest()
    record_dict["age"] = sha256(str(record.age).encode()).hexdigest()

    # Generate submission_id if not provided
    if not record.submission_id:
        now = datetime.utcnow()
        date_hour_str = now.strftime("%Y%m%d%H")
        submission_id_str = record.email + date_hour_str
        record_dict["submission_id"] = sha256(submission_id_str.encode()).hexdigest()

    # Enrich with server-side info
    record_dict["received_at"] = datetime.utcnow().isoformat() + "Z"
    record_dict["ip_address"] = request.remote_addr

    # Persist to storage
    append_json_line(record_dict)

    return jsonify({"status": "ok"}), 201

if __name__ == "__main__":
    app.run(port=0, debug=True)
