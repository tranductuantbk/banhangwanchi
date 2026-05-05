import streamlit as st
import pandas as pd
from sqlalchemy import text
from fpdf import FPDF
import re
import requests
import tempfile
import os
from datetime import datetime

st.set_page_config(page_title="WANCHI Admin - Quản lý Kho", layout="wide")
conn = st.connection("postgresql", type="sql", pool_pre_ping=True)

# ==========================================
# KHỐI TỰ ĐỘNG SỬA LỖI & THAY ĐỔI CẤU TRÚC DATABASE
# ==========================================
try:
    with conn.session as s:
        # Thêm cột quy cách nếu chưa có
        s.execute(text("ALTER TABLE agency_products ADD COLUMN IF NOT EXISTS unit_per_pack INTEGER DEFAULT 100;"))
        s.execute(text("ALTER TABLE company_products ADD COLUMN IF NOT EXISTS unit_per_pack INTEGER DEFAULT 100;"))
        
        # Gỡ bỏ ràng buộc Unique cũ của product_code (Mã SP được phép trùng)
        s.execute(text("ALTER TABLE agency_products DROP CONSTRAINT IF EXISTS agency_products_product_code_key CASCADE;"))
        s.execute(text("ALTER TABLE company_products DROP CONSTRAINT IF EXISTS company_products_product_code_key CASCADE;"))
        s.commit()
except Exception as e:
    pass # Bỏ qua lỗi nhẹ nếu các khóa này đã được xóa từ trước

# --- KIỂM TRA TÀI NGUYÊN ---
available_font = None
for f in ["arial.ttf", "Arial.ttf", "ARIAL.TTF", "arial_dl.ttf"]:
    if os.path.exists(f):
        available_font = f
        break

if not available_font:
    try:
        r = requests.get("https://github.com/matomo-org/travis-scripts/raw/master/fonts/Arial.ttf", timeout=5)
        with open("arial_dl.ttf", "wb") as f: f.write(r.content)
        available_font = "arial_dl.ttf"
    except: pass

LOGO_FILES = ["logo.png", "logo.jpg", "LOGO.png", "LOGO.jpg"]
available_logo = next((l for l in LOGO_FILES if os.path.exists(l)), None)

# --- HÀM HỖ TRỢ ---
def convert_drive_link(raw_url):
    if not raw_url: return ""
    match = re.search(r"(?:/d/|id=)([a-zA-Z0-9_-]+)", str(raw_url))
    return f"https://drive.google.com/uc?export=download&id={match.group(1)}" if match else raw_url

def register_wanchi_font(pdf):
    if available_font:
        try:
            pdf.add_font("ArialVN", style="", fname=available_font)
            pdf.add_font("ArialVN", style="B", fname=available_font)
            return "ArialVN"
        except: pass
    return "Helvetica"

class WanchiPDF(FPDF):
    def __init__(self, quote_type="CÔNG TY"):
        super().__init__()
        self.quote_type = quote_type
        self.font_wanchi = register_wanchi_font(self)

    def header_wanchi(self):
        if available_logo: self.image(available_logo, x=10, y=8, h=15)
        else:
            self.set_font(self.font_wanchi, "B", 18)
            self.cell(100, 10, "WANCHI", border=0, align='L')
        self.set_font(self.font_wanchi, "B", 10)
        self.set_xy(130, 8)
        self.multi_cell(70, 5, txt=f"BẢNG BÁO GIÁ {self.quote_type}\nTháng {datetime.now().strftime('%m/%Y')}\nHotline: 0902.580.828", align='R')
        self.ln(10)

# --- THIẾT KẾ GRID ---
def export_pro_pdf(df, mode="AGENCY"):
    title = "ĐẠI LÝ" if mode == "AGENCY" else "CÔNG TY"
    pdf = WanchiPDF(quote_type=title)
    pdf.add_page()
    pdf.header_wanchi()
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font(pdf.font_wanchi, "B", 10)
    
    if mode == "COMPANY":
        widths = [35, 30, 55, 35, 20, 15]
        headers = ["Hình ảnh", "Mã SP", "Diễn giải", "Kích thước", "Đơn giá", "Cái"]
        row_h = 26
    else:
        widths = [35, 70, 45, 20, 20]
        headers = ["Mã SP", "Diễn giải", "Kích thước", "Đơn giá", "Cái"]
        row_h = 12
    
    for i, head in enumerate(headers):
        pdf.cell(widths[i], 10, txt=head, border=1, fill=True, align='C')
    pdf.ln()
    
    pdf.set_font(pdf.font_wanchi, "", 9)
    for _, row in df.iterrows():
        if pdf.get_y() + row_h > 275:
            pdf.add_page()
            pdf.set_fill_color(220, 220, 220)
            pdf.set_font(pdf.font_wanchi, "B", 10)
            for i, head in enumerate(headers): 
                pdf.cell(widths[i], 10, txt=head, border=1, fill=True, align='C')
            pdf.ln()
            pdf.set_font(pdf.font_wanchi, "", 9)

        x, y = pdf.get_x(), pdf.get_y()
        
        cx = x
        for w in widths:
            pdf.rect(cx, y, w, row_h)
            cx += w
            
        cx = x
        if mode == "COMPANY":
            img_url = row.get('image_data', '')
            if img_url:
                try:
                    res = requests.get(img_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7)
                    if res.status_code == 200 and 'text/html' not in res.headers.get('Content-Type', ''):
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(res.content)
                            tmp_path = tmp.name
                        pdf.image(tmp_path, x=cx+1, y=y+1, w=widths[0]-2, h=row_h-2)
                        os.remove(tmp_path)
                except: pass
            cx += widths[0]
            w_list = widths[1:]
        else: w_list = widths

        pdf.set_xy(cx, y + (row_h/2 - 2.5))
        pdf.multi_cell(w_list[0], 5, txt=str(row.get('product_code', '')), border=0, align='C')
        cx += w_list[0]

        pdf.set_xy(cx + 1, y + 2)
        pdf.multi_cell(w_list[1] - 2, 5, txt=str(row.get('name', '')), border=0, align='C')
        cx += w_list[1]

        pdf.set_xy(cx + 1, y + 2)
        pdf.multi_cell(w_list[2] - 2, 5, txt=str(row.get('size', '')), border=0, align='C')
        cx += w_list[2]

        price_val = row.get('price_company') if mode == "COMPANY" else row.get('price_agency')
        price_str = f"{int(price_val):,}".replace(",", ".") if pd.notna(price_val) else "0"
        pdf.set_xy(cx, y + (row_h/2 - 2.5))
        pdf.cell(w_list[3], 5, txt=price_str, border=0, align='C')
        cx += w_list[3]

        unit_str = "1 cái" if mode == "COMPANY" else f"{row.get('unit_per_pack', 100)} cái"
        pdf.set_xy(cx, y + (row_h/2 - 2.5))
        pdf.cell(w_list[4], 5, txt=unit_str, border=0, align='C')

        pdf.set_xy(x, y + row_h)
    return bytes(pdf.output())

# --- GIAO DIỆN ---
if 'is_admin' not in st.session_state: st.session_state.is_admin = False
st.title("⚙️ Quản lý Báo giá WANCHI Pro")

if not st.session_state.is_admin:
    pwd = st.text_input("Mật khẩu Admin", type="password")
    if st.button("Đăng nhập"):
        if pwd == st.secrets["admin"]["password"]:
            st.session_state.is_admin = True
            st.rerun()
else:
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Nhập SP Đại lý", "🏢 Nhập giá SP Công ty", "📈 Danh sách SP Công ty", "📜 Đơn hàng"])
    
    with tab1:
        with st.form("agency_add"):
            c1, c2 = st.columns(2)
            code = c1.text_input("Mã sản phẩm (Có thể trùng)")
            name = c2.text_input("Tên diễn giải (Bắt buộc KHÔNG trùng)")
            size, price = c1.text_input("Kích thước"), c2.number_input("Giá gốc Đại lý", min_value=0)
            pack = st.number_input("Quy cách Lốc", value=100)
            
            if st.form_submit_button("Lưu kho Đại lý"):
                if not name.strip():
                    st.error("Tên diễn giải không được để trống!")
                else:
                    try:
                        with conn.session as s:
                            # Phương pháp Python Logic: Tránh lỗi IntegrityError hoàn toàn
                            check_query = text("SELECT id FROM agency_products WHERE name = :n")
                            exists = s.execute(check_query, {"n": name}).fetchone()
                            
                            if exists:
                                # Nếu đã có tên này -> Cập nhật
                                s.execute(text("""
                                    UPDATE agency_products 
                                    SET price_agency=:p, product_code=:c, size=:s, unit_per_pack=:pk 
                                    WHERE name=:n
                                """), {"c":code, "n":name, "s":size, "p":price, "pk":pack})
                            else:
                                # Nếu chưa có tên này -> Thêm mới
                                s.execute(text("""
                                    INSERT INTO agency_products (product_code, name, size, price_agency, unit_per_pack) 
                                    VALUES (:c, :n, :s, :p, :pk)
                                """), {"c":code, "n":name, "s":size, "p":price, "pk":pack})
                            s.commit()
                        st.success(f"Đã lưu thành công diễn giải: {name}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Lỗi: {e}")
        
        df_a = conn.query("SELECT * FROM agency_products ORDER BY id DESC", ttl=0)
        if not df_a.empty:
            st.dataframe(df_a, use_container_width=True)
            if st.button("🚀 XUẤT PDF ĐẠI LÝ"):
                pdf = export_pro_pdf(df_a, mode="AGENCY")
                st.download_button("📥 TẢI PDF", data=pdf, file_name="Bao_Gia_DaiLy.pdf")
            
            st.divider()
            st.subheader("🗑️ Xóa sản phẩm Đại lý")
            del_opts_a = {row['name']: f"[{row['product_code']}] {row['name']}" for _, row in df_a.iterrows()}
            sel_del_a = st.selectbox("Chọn Diễn giải SP Đại lý cần xóa:", options=list(del_opts_a.keys()), format_func=lambda x: del_opts_a[x])
            with st.popover("🗑️ Xác nhận xóa Đại lý"):
                st.warning(f"Xóa vĩnh viễn sản phẩm: {sel_del_a}?")
                if st.button("Xác nhận xóa ngay", key="btn_del_a"):
                    with conn.session as s:
                        s.execute(text("DELETE FROM agency_products WHERE name=:n"), {"n": sel_del_a})
                        s.commit()
                    st.rerun()

    with tab2:
        df_a2 = conn.query("SELECT * FROM agency_products", ttl=0)
        if not df_a2.empty:
            sel = st.selectbox("Chọn sản phẩm cần nhập giá công ty:", options=df_a2['name'])
            target = df_a2[df_a2['name'] == sel].iloc[0]
            
            with st.form("co_form"):
                st.write(f"Đang cập nhật cho: **[{target['product_code']}] {target['name']}**")
                price_company = st.number_input("Nhập giá Công ty (VNĐ)", min_value=0, value=int(target.get('price_agency', 0)))
                
                raw_img = st.text_input("Link ảnh thiết kế (Chú ý: Nhớ bật quyền 'Bất kỳ ai có liên kết' trên Drive):")
                if st.form_submit_button("Xác nhận"):
                    final_i = convert_drive_link(raw_img)
                    try:
                        with conn.session as s:
                            # Phương pháp Python Logic: Tránh lỗi IntegrityError hoàn toàn
                            check_query = text("SELECT id FROM company_products WHERE name = :n")
                            exists = s.execute(check_query, {"n": target['name']}).fetchone()
                            
                            if exists:
                                # Cập nhật
                                s.execute(text("""
                                    UPDATE company_products 
                                    SET price_company=:p, product_code=:c, image_data=:i 
                                    WHERE name=:n
                                """), {"c":target['product_code'], "n":target['name'], "s":target['size'], "p":price_company, "i":str(final_i)})
                            else:
                                # Thêm mới
                                s.execute(text("""
                                    INSERT INTO company_products (product_code, name, size, price_company, image_data) 
                                    VALUES (:c, :n, :s, :p, :i)
                                """), {"c":target['product_code'], "n":target['name'], "s":target['size'], "p":price_company, "i":str(final_i)})
                            s.commit()
                        st.success("Đã cập nhật kho Công ty!")
                    except Exception as e:
                        st.error(f"❌ Lỗi: {e}")

    with tab3:
        df_c = conn.query("SELECT * FROM company_products ORDER BY id DESC", ttl=0)
        if not df_c.empty:
            st.dataframe(df_c[['product_code', 'name', 'size', 'price_company']], use_container_width=True)
            if st.button("🚀 XUẤT PDF CÔNG TY"):
                with st.spinner("Đang chèn ảnh và đóng gói PDF (Nếu không thấy ảnh, vui lòng kiểm tra lại quyền Share của link Google Drive)..."):
                    pdf_c = export_pro_pdf(df_c, mode="COMPANY")
                    st.download_button("📥 TẢI PDF BÁO GIÁ CÔNG TY", data=pdf_c, file_name="Bao_Gia_CongTy.pdf")
            
            st.divider()
            st.subheader("🗑️ Xóa sản phẩm Công ty")
            del_opts_c = {row['name']: f"[{row['product_code']}] {row['name']}" for _, row in df_c.iterrows()}
            sel_del_c = st.selectbox("Chọn Diễn giải SP Công ty cần xóa:", options=list(del_opts_c.keys()), format_func=lambda x: del_opts_c[x])
            with st.popover("🗑️ Xác nhận xóa Công ty"):
                st.warning(f"Xóa SP Công ty: {sel_del_c}? (Bên Đại lý vẫn giữ nguyên)")
                if st.button("Xác nhận xóa ngay", key="btn_del_c"):
                    with conn.session as s:
                        s.execute(text("DELETE FROM company_products WHERE name=:n"), {"n": sel_del_c})
                        s.commit()
                    st.rerun()

    with tab4:
        df_o = conn.query("SELECT * FROM orders ORDER BY order_date DESC", ttl=0)
        if not df_o.empty:
            for _, row in df_o.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.write(f"👤 **{row['customer_name']}** - 📞 {row['customer_phone']}")
                    c2.write(f"💰 {int(row['total_amount']):,} đ")
                    if c3.button("🗑️ Xóa đơn", key=f"del_ord_{row['id']}"):
                        with conn.session as s:
                            s.execute(text("DELETE FROM orders WHERE id=:id"), {"id": row['id']})
                            s.commit()
                        st.rerun()
                    with st.expander("Xem chi tiết"): st.text(row['order_items'])
