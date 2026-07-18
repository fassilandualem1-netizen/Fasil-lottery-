from football_api import get_football_matches # ከፈጠርከው ፋይል አስመጣ

@real_sports_bp.route('/api/get-real-matches')
def get_real_matches():
    matches = get_football_matches()
    return jsonify({"status": "success", "data": matches})
