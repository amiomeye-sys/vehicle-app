import os
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, send_file, redirect, url_for
from PIL import Image
from rembg import remove, new_session
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

try:
    fast_session = new_session("u2netp")
except Exception:
    fast_session = None

SUBMITTED_DATA_STORE = []

TEMPLATE_TEXT = (
    "I, {owner_name} S/W/D of... {owner_father} Resident of... {owner_address} "
    "do hereby declare that I am registered owner of vehicle bearing Registration No- {gari_number} "
    "Engine No- {engine_no} Chassis No- {chassis_no} "
    "further declare that I hereby authorise to {driver_name} Son/W/D Of... {driver_father} "
    "Resident Of... {driver_address} "
    "Having Driving licence No- {license_no} Do drive my above noted obey authorised "
    "To the above person to drive the said vehicle on road and handed over the vehicle along with "
    "relevant documents to the above authorised person for driving the vehicle on road, I do hereby "
    "undertake to declare that, if any things happen on road during the playing of the vehicle the "
    "above mention person/driver will face and maintain all matter i.e. motor vehicles dept./police/ court etc."
)

def calculate_valid_upto(date_str):
    try:
        parts = date_str.strip().split('/')
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        month += 6
        if month > 12:
            month -= 12
            year += 1
        day -= 1
        if day == 0:
            month -= 1
            if month == 0:
                month = 12
                year -= 1
            day = 31 if month in [1, 3, 5, 7, 8, 10, 12] else (30 if month in [4, 6, 9, 11] else 28)
        return f"{day:02d}/{month:02d}/{year}"
    except Exception:
        return ""

def process_and_save_photo(file_obj, data_id):
    in_img = Image.open(file_obj.stream)
    out_img = remove(in_img, session=fast_session) if fast_session else remove(in_img)
    bg = Image.new("RGBA", out_img.size, (255, 255, 255, 255))
    final_photo = Image.alpha_composite(bg, out_img).convert("RGB")
    photo_filename = f"photo_{data_id}_{datetime.now().timestamp()}.png"
    photo_save_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
    final_photo.save(photo_save_path)
    return photo_save_path

def generate_pdf_file(data, output_path):
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    start_y = height - (15.5 * cm)
    left_margin = 5 * cm

    c.setFont("Times-Roman", 12)
    c.drawCentredString(width / 2.0, start_y, "TO WHOM IT MAY CONCERN")
    c.setLineWidth(1)
    c.line(width / 2.0 - 80, start_y - 3, width / 2.0 + 80, start_y - 3)

    c.drawCentredString(width / 2.0, start_y - 18, "AUTHORITY LETTER")
    c.line(width / 2.0 - 65, start_y - 21, width / 2.0 + 65, start_y - 21)

    input_date = data.get('date', datetime.now().strftime("%d/%m/%Y"))
    valid_date = calculate_valid_upto(input_date)

    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - 55, start_y, f"DATE-{input_date}")
    c.drawRightString(width - 55, start_y - 14, f"VALID UPTO-{valid_date}")

    clean_data = {}
    for key in ["owner_name", "owner_father", "owner_address", "gari_number", "engine_no", "chassis_no", "driver_name", "driver_father", "driver_address", "license_no"]:
        val = data.get(key, "").strip()
        val = re.sub(r'[\s,\.]+$', '', val)
        if key in ["owner_name", "driver_name", "owner_father", "driver_father"]:
            formatted_val = val.title()
        elif key in ["owner_address", "driver_address"]:
            formatted_val = ", ".join([p.strip().title() for p in val.split(",") if p.strip()])
        elif key == "gari_number":
            raw_gari = val.upper().replace("-", "").strip()
            match = re.match(r'^([A-Z]+)(\d+)([A-Z]+)(\d+)$', raw_gari)
            formatted_val = f"{match.group(1)}-{match.group(2)}{match.group(3)}-{match.group(4)}" if match else raw_gari
        else:
            formatted_val = val.upper()
        clean_data[key] = formatted_val + "," if formatted_val else ""

    formatted_text = TEMPLATE_TEXT.format(**clean_data)
    styles = getSampleStyleSheet()
    style = ParagraphStyle('StampStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=11, leading=16)

    current_y = start_y - 21 - (1.0 * cm)
    p = Paragraph(formatted_text, style)
    p.wrap(width - left_margin - (2.0 * cm), height)
    p.drawOn(c, left_margin, current_y - p.height)

    sig_y = 20
    photo_y = sig_y + 15
    photo_w, photo_h = 2.5 * cm, 3.5 * cm
    shifted_left = left_margin + (1.0 * cm)

    photo_path = data.get('photo_path')
    if photo_path and os.path.exists(photo_path):
        try:
            c.drawImage(photo_path, shifted_left, photo_y, width=photo_w, height=photo_h)
            c.setLineWidth(0.8)
            c.rect(shifted_left, photo_y, photo_w, photo_h, stroke=1, fill=0)
        except Exception:
            pass

    c.setFont("Helvetica-Bold", 12)
    c.drawString(shifted_left, sig_y, "Signature of Driver")
    c.drawString(width - 200, sig_y, "Signature of Regd. Owner")
    c.showPage()
    c.save()

@app.route('/form', methods=['GET', 'POST'])
def client_form():
    if request.method == 'POST':
        data_id = len(SUBMITTED_DATA_STORE) + 1
        data = {
            'id': data_id,
            'owner_name': request.form.get('owner_name', ''),
            'owner_father': request.form.get('owner_father', ''),
            'owner_address': request.form.get('owner_address', ''),
            'gari_number': request.form.get('gari_number', ''),
            'engine_no': request.form.get('engine_no', ''),
            'chassis_no': request.form.get('chassis_no', ''),
            'driver_name': request.form.get('driver_name', ''),
            'driver_father': request.form.get('driver_father', ''),
            'driver_address': request.form.get('driver_address', ''),
            'license_no': request.form.get('license_no', ''),
            'date': datetime.now().strftime("%d/%m/%Y"),
            'photo_path': None
        }

        file = request.files.get('driver_photo')
        if file and file.filename != '':
            data['photo_path'] = process_and_save_photo(file, data_id)

        SUBMITTED_DATA_STORE.append(data)
        return render_template('client_form.html', success=True)

    return render_template('client_form.html', success=False)

@app.route('/admin')
def admin_dashboard():
    today_str = datetime.now().strftime("%d/%m/%Y")
    search_date_raw = request.args.get('search_date', '').strip()
    search_gari = request.args.get('search_gari', '').strip().lower()

    search_date = ""
    if search_date_raw:
        try:
            search_date = datetime.strptime(search_date_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            search_date = search_date_raw

    filtered = []
    if search_date or search_gari:
        for item in SUBMITTED_DATA_STORE:
            match_date = (item['date'] == search_date) if search_date else True
            match_gari = (search_gari in item['gari_number'].lower()) if search_gari else True
            if match_date and match_gari:
                filtered.append(item)
    else:
        filtered = [item for item in SUBMITTED_DATA_STORE if item['date'] == today_str]

    return render_template('admin_dashboard.html', submissions=filtered, today=today_str, search_date=search_date_raw, search_gari=request.args.get('search_gari', ''))

@app.route('/admin/edit/<int:data_id>', methods=['GET', 'POST'])
def edit_submission(data_id):
    item = next((x for x in SUBMITTED_DATA_STORE if x['id'] == data_id), None)
    if not item:
        return "Record Not Found", 404

    if request.method == 'POST':
        item['owner_name'] = request.form.get('owner_name', item['owner_name'])
        item['owner_father'] = request.form.get('owner_father', item['owner_father'])
        item['owner_address'] = request.form.get('owner_address', item['owner_address'])
        item['gari_number'] = request.form.get('gari_number', item['gari_number'])
        item['engine_no'] = request.form.get('engine_no', item['engine_no'])
        item['chassis_no'] = request.form.get('chassis_no', item['chassis_no'])
        item['driver_name'] = request.form.get('driver_name', item['driver_name'])
        item['driver_father'] = request.form.get('driver_father', item['driver_father'])
        item['driver_address'] = request.form.get('driver_address', item['driver_address'])
        item['license_no'] = request.form.get('license_no', item['license_no'])
        
        new_date = request.form.get('date')
        if new_date:
            try:
                item['date'] = datetime.strptime(new_date, "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                item['date'] = new_date

        file = request.files.get('driver_photo')
        if file and file.filename != '':
            item['photo_path'] = process_and_save_photo(file, item['id'])

        return redirect(url_for('admin_dashboard'))

    try:
        formatted_date = datetime.strptime(item['date'], "%d/%m/%Y").strftime("%Y-%m-%d")
    except Exception:
        formatted_date = item['date']

    return render_template('edit_submission.html', item=item, formatted_date=formatted_date)

@app.route('/generate_pdf/<int:data_id>')
def pdf_preview(data_id):
    item = next((x for x in SUBMITTED_DATA_STORE if x['id'] == data_id), None)
    if not item:
        return "Not found", 404
    
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f"doc_{data_id}.pdf")
    generate_pdf_file(item, pdf_path)
    return send_file(pdf_path, mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)