import streamlit as st
import pandas as pd
from fpdf import FPDF
from sqlalchemy import text
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
import os
import base64
import re

st.set_page_config(page_title="Bán Hàng Wanchi", layout="wide")

# ==========================================
# CÔNG CỤ ẨN BÊN THANH SIDEBAR (DÀNH CHO ADMIN)
# ==========================================
with st.sidebar:
    st.header("🛠️ Tiện ích xưởng")
    with st.expander("🔗 Đổi Link Ảnh Google Drive", expanded=False):
        st.caption("Dùng để lấy link trực tiếp dán vào trang Thêm Sản Phẩm.")
        raw_link = st.text_input("Dán link ảnh từ Drive:")
        if raw_link:
            if "/file/d/" in raw_link:
                match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", raw_link)
                if match:
                    img_link = f"https://drive.google.com/thumbnail?id={match.group(1)}&sz=w1000"
                    st.success("✅ Copy link ở khung đen bên dưới:")
                    st.code(img_link)
            elif "/folders/" in raw_link:
                st.error("❌ Đây là link THƯ MỤC. Hãy mở to ảnh ra và copy lại.")
            elif "drive.google.com/uc?id=" in raw_link:
                st.info("Link này đã chuẩn sẵn rồi!")
                st.code(raw_link)
            else:
                st.error("❌ Link chưa đúng định dạng /file/d/")

if 'cart' not in st.session_state:
    st.session_state.cart = {}
if 'cust_name' not in st.session_state:
    st.session_state.cust_name = ""
if 'cust_phone' not in st.session_state:
    st.session_state.cust_phone = ""
if 'saved_order' not in st.session_state:
    st.session_state.saved_order = False

conn = st.connection("postgresql", type="sql", pool_pre_ping=True)

def save_order_to_db(name, phone, total, items_list, file_type, file_bytes):
    try:
        b64_data = base64.b64encode(file_bytes).decode('utf-8')
        items_str = "\n".join([f"- {i['Tên']} (SL: {i['SL']})" for i in items_list])
        
        with conn.session as s:
            s.execute(text("""
                INSERT INTO orders (customer_name, customer_phone, total_amount, order_items, file_type, file_data) 
                VALUES (:n, :p, :t, :it, :ft, :fd)
            """), {"n": name, "p": phone, "t": total, "it": items_str, "ft": file_type, "fd": b64_data})
            s.commit()
    except: pass

st.title("🏭 Cổng Đặt Hàng WANCHI")
tab1, tab2 = st.tabs(["📦 Danh sách sản phẩm", "🛒 Giỏ hàng & Chốt đơn"])

with tab1:
    try:
        df_products = conn.query("SELECT * FROM products ORDER BY id", ttl=0)
        if df_products.empty:
            st.info("Hiện tại chưa có sản phẩm nào. Vui lòng vào trang Admin để thêm.")
        else:
            # --- HEADER DẠNG BẢNG GIỐNG FILE PDF ---
            h1, h2, h3, h4, h5, h6, h7 = st.columns([2, 2, 3, 2, 2, 2, 2])
            with h1: st.markdown("**Hình ảnh**")
            with h2: st.markdown("**Mã SP**")
            with h3: st.markdown("**Diễn giải**")
            with h4: st.markdown("**Kích thước**")
            with h5: st.markdown("**Đơn giá**")
            with h6: st.markdown("**Số lượng**")
            with h7: st.markdown("**Thao tác**")
            st.divider()

            # --- DANH SÁCH SẢN PHẨM TRẢI NGANG ---
            for i, row in df_products.iterrows():
                c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 2, 3, 2, 2, 2, 2])
                
                with c1:
                    # Nút Xem thông tin (Popover) thay thế cho ảnh tĩnh
                    with st.popover("🔍 Xem thông tin"):
                        # Bộ lọc link ảnh chuẩn
                        raw_img_url = str(row['image_data']).strip() if pd.notna(row['image_data']) else ""
                        display_url = ""
                        if raw_img_url:
                            match = re.search(r"(?<=/d/)[a-zA-Z0-9_-]+|(?<=id=)[a-zA-Z0-9_-]+", raw_img_url)
                            if match:
                                display_url = f"https://drive.google.com/thumbnail?id={match.group(0)}&sz=w1000"
                            else:
                                display_url = raw_img_url
                        
                        # Hiện 2 hình ảnh theo yêu cầu 
                        img_col1, img_col2 = st.columns(2)
                        with img_col1:
                            if display_url: st.image(display_url, use_container_width=True)
                            else: st.write("*(Chưa có ảnh)*")
                        with img_col2:
                            if display_url: st.image(display_url, use_container_width=True) # Hiện 2 ảnh giống nhau tạm thời
                            else: st.write("*(Chưa có ảnh)*")
                            
                        # Dòng ghi thông tin sản phẩm
                        st.write(f"📝 **Chi tiết:** {row['description'] if pd.notna(row['description']) and str(row['description']).strip() != '' else 'Đang cập nhật'}")

                # Các cột thông tin tương ứng như bảng báo giá
                c2.write(row['product_code'])
                c3.write(row['name'])
                c4.write(row['size'])
                
                price = row['price'] if pd.notna(row['price']) else 0
                c5.write(f"**{int(price):,} đ**")
                
                with c6:
                    # Cột nhập số lượng
                    qty = st.number_input("SL", min_value=1, value=100, step=10, key=f"qty_{row['id']}", label_visibility="collapsed")
                
                with c7:
                    # Cột nút bấm thêm giỏ hàng
                    if st.button("🛒 Thêm giỏ", key=f"add_{row['id']}", use_container_width=True):
                        code = row['product_code']
                        st.session_state.cart[code] = st.session_state.cart.get(code, 0) + qty
                        st.session_state.saved_order = False
                        st.toast("✅ Đã thêm vào giỏ hàng!")
                
                st.divider() # Dòng kẻ ngang phân cách từng sản phẩm

    except Exception as e:
        st.error(f"Lỗi kết nối CSDL: {e}")

# ==========================================
# TAB 2: GIỎ HÀNG VÀ CHỐT ĐƠN (GIỮ NGUYÊN)
# ==========================================
with tab2:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📋 Thông tin người mua")
        st.session_state.cust_name = st.text_input("Tên người mua", st.session_state.cust_name)
        st.session_state.cust_phone = st.text_input("Số điện thoại", st.session_state.cust_phone)
        if not st.session_state.cust_name or not st.session_state.cust_phone:
            st.warning("⚠️ Vui lòng điền tên và SĐT để chốt đơn.")
    
    with col2:
        st.subheader("🛒 Chi tiết đơn hàng")
        if not st.session_state.cart:
            st.info("Giỏ hàng của bạn đang trống.")
        else:
            total_price = 0
            cart_list = []
            try:
                df_products_cart = conn.query("SELECT * FROM products", ttl=0)
                for code, qty in st.session_state.cart.items():
                    prod_match = df_products_cart[df_products_cart['product_code'] == code]
                    if not prod_match.empty:
                        prod = prod_match.iloc[0]
                        price = prod['price'] if pd.notna(prod['price']) else 0
                        line_total = int(price) * qty
                        total_price += line_total
                        cart_list.append({"Mã": code, "Tên": prod['name'], "SL": qty, "Tiền": line_total})
                        st.write(f"- **{prod['name']}** (SL: {qty}) : {line_total:,} đ")
                st.write(f"### Tổng cộng: {total_price:,} đ")
            except: pass

            if st.session_state.cust_name and st.session_state.cust_phone and cart_list:
                st.divider()
                st.subheader("🎉 Chọn định dạng tải đơn hàng:")
                col_btn_pdf, col_btn_img = st.columns(2)
                
                # XUẤT PDF
                pdf_bytes = None
                try:
                    pdf = FPDF()
                    pdf.add_page()
                    if os.path.exists("arial.ttf"):
                        pdf.add_font("Arial", style="", fname="arial.ttf")
                        pdf.set_font("Arial", size=12)
                    try:
                        pdf.image("logo.png", x=10, y=10, w=45) 
                    except:
                        try:
                            pdf.image("logo.jpg", x=10, y=10, w=45)
                        except:
                            pdf.set_font("Arial", size=18)
                            pdf.cell(45, 10, txt="WANCHI", align="L")
                    
                    pdf.set_font("Arial", size=10)
                    pdf.set_xy(65, 12)
                    pdf.cell(0, 5, txt="775 Võ Hữu Lợi, Xã Lê Minh Xuân, Huyện Bình Chánh, TP.HCM", ln=1)
                    pdf.set_xy(65, 18)
                    pdf.cell(0, 5, txt="SĐT: 0902.580.828 - 0937.572.577", ln=1)
                    pdf.ln(15)
                    pdf.set_font("Arial", size=18)
                    pdf.cell(0, 10, txt="PHIẾU ĐẶT HÀNG", ln=1, align="C")
                    pdf.set_font("Arial", size=11)
                    pdf.cell(0, 6, txt=f"Ngày: {datetime.now().strftime('%d/%m/%Y')}", ln=1, align="C")
                    pdf.ln(8)
                    pdf.set_font("Arial", size=11)
                    pdf.cell(0, 6, txt=f"Khách hàng: {st.session_state.cust_name.upper()}", ln=1)
                    pdf.cell(0, 6, txt=f"Điện thoại: {st.session_state.cust_phone}", ln=1)
                    pdf.ln(5)
                    pdf.set_fill_color(230, 230, 230)
                    pdf.set_font("Arial", size=10)
                    pdf.cell(15, 8, txt="STT", border=1, align="C", fill=True)
                    pdf.cell(85, 8, txt="Tên Sản Phẩm", border=1, align="C", fill=True)
                    pdf.cell(15, 8, txt="SL", border=1, align="C", fill=True)
                    pdf.cell(35, 8, txt="Đơn Giá", border=1, align="C", fill=True)
                    pdf.cell(40, 8, txt="Thành Tiền", border=1, align="C", fill=True)
                    pdf.ln()
                    for i, item in enumerate(cart_list, 1):
                        pdf.cell(15, 8, txt=str(i), border=1, align="C")
                        pdf.cell(85, 8, txt=item['Tên'], border=1)
                        pdf.cell(15, 8, txt=str(item['SL']), border=1, align="C")
                        don_gia = int(item['Tiền'] / item['SL'])
                        pdf.cell(35, 8, txt=f"{don_gia:,}".replace(",", "."), border=1, align="R")
                        pdf.cell(40, 8, txt=f"{item['Tiền']:,}".replace(",", "."), border=1, align="R")
                        pdf.ln()
                    pdf.cell(150, 8, txt="TỔNG CỘNG:", border=1, align="R")
                    pdf.cell(40, 8, txt=f"{total_price:,}".replace(",", "."), border=1, align="R")
                    pdf_bytes = bytes(pdf.output())
                except: pass

                # XUẤT ẢNH
                img_bytes = None
                try:
                    img_height = max(550, 350 + len(cart_list)*40 + 50)
                    img = Image.new('RGB', (800, img_height), color=(255, 255, 255))
                    draw = ImageDraw.Draw(img)
                    try:
                        font_title = ImageFont.truetype("arial.ttf", 32)
                        font_text = ImageFont.truetype("arial.ttf", 16)
                        font_bold = ImageFont.truetype("arial.ttf", 16)
                    except:
                        font_title = font_text = font_bold = ImageFont.load_default()
                    try:
                        logo = Image.open("logo.png").convert("RGBA")
                        logo = logo.resize((140, 50))
                        img.paste(logo, (40, 30), logo)
                    except:
                        try:
                            logo = Image.open("logo.jpg").convert("RGBA")
                            logo = logo.resize((140, 50))
                            img.paste(logo, (40, 30), logo)
                        except:
                            draw.text((40, 30), "WANCHI", fill=(0, 0, 0), font=font_title)
                    draw.text((220, 35), "775 Võ Hữu Lợi, Xã Lê Minh Xuân, Bình Chánh, TP.HCM", fill=(0,0,0), font=font_text)
                    draw.text((220, 60), "SĐT: 0902.580.828 - 0937.572.577", fill=(0,0,0), font=font_text)
                    draw.text((280, 130), "PHIẾU ĐẶT HÀNG", fill=(0, 0, 0), font=font_title)
                    draw.text((340, 180), f"Ngày: {datetime.now().strftime('%d/%m/%Y')}", fill=(0,0,0), font=font_text)
                    draw.text((40, 230), f"Khách hàng: {st.session_state.cust_name.upper()}", fill=(0,0,0), font=font_bold)
                    draw.text((40, 260), f"Điện thoại: {st.session_state.cust_phone}", fill=(0,0,0), font=font_bold)
                    y_pos = 300
                    draw.rectangle([40, y_pos, 760, y_pos+35], fill=(230, 230, 230), outline=(0,0,0))
                    draw.text((50, y_pos+8), "STT", fill=(0,0,0), font=font_bold)
                    draw.text((100, y_pos+8), "Tên Sản Phẩm", fill=(0,0,0), font=font_bold)
                    draw.text((450, y_pos+8), "SL", fill=(0,0,0), font=font_bold)
                    draw.text((520, y_pos+8), "Đơn Giá", fill=(0,0,0), font=font_bold)
                    draw.text((640, y_pos+8), "Thành Tiền", fill=(0,0,0), font=font_bold)
                    y_pos += 35
                    for i, item in enumerate(cart_list, 1):
                        draw.rectangle([40, y_pos, 760, y_pos+35], outline=(0,0,0))
                        draw.text((55, y_pos+8), str(i), fill=(0,0,0), font=font_text)
                        draw.text((100, y_pos+8), item['Tên'][:40], fill=(0,0,0), font=font_text)
                        draw.text((450, y_pos+8), str(item['SL']), fill=(0,0,0), font=font_text)
                        don_gia = int(item['Tiền'] / item['SL'])
                        draw.text((520, y_pos+8), f"{don_gia:,}".replace(",", "."), fill=(0,0,0), font=font_text)
                        draw.text((640, y_pos+8), f"{item['Tiền']:,}".replace(",", "."), fill=(0,0,0), font=font_text)
                        y_pos += 35
                    draw.rectangle([40, y_pos, 760, y_pos+40], outline=(0,0,0))
                    draw.text((450, y_pos+10), "TỔNG CỘNG:", fill=(0,0,0), font=font_bold)
                    draw.text((640, y_pos+10), f"{total_price:,}".replace(",", "."), fill=(0,0,0), font=font_bold)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=95)
                    img_bytes = buf.getvalue()
                except: pass

                with col_btn_pdf:
                    if pdf_bytes:
                        if st.download_button("📄 Lưu file PDF", data=pdf_bytes, file_name=f"Phieu_{st.session_state.cust_name}.pdf", mime="application/pdf", use_container_width=True):
                            if not st.session_state.saved_order:
                                save_order_to_db(st.session_state.cust_name, st.session_state.cust_phone, total_price, cart_list, "pdf", pdf_bytes)
                                st.session_state.saved_order = True
                                
                with col_btn_img:
                    if img_bytes:
                        if st.download_button("🖼️ Lưu Ảnh JPG", data=img_bytes, file_name=f"Phieu_{st.session_state.cust_name}.jpg", mime="image/jpeg", use_container_width=True):
                            if not st.session_state.saved_order:
                                save_order_to_db(st.session_state.cust_name, st.session_state.cust_phone, total_price, cart_list, "jpg", img_bytes)
                                st.session_state.saved_order = True
