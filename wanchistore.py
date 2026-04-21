import streamlit as st
import pandas as pd
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
from fpdf import FPDF
from sqlalchemy import text
from datetime import datetime

st.set_page_config(page_title="Bán Hàng Wanchi", layout="wide")

# Khởi tạo Giỏ hàng trong bộ nhớ tạm
if 'cart' not in st.session_state:
    st.session_state.cart = {}
if 'cust_name' not in st.session_state:
    st.session_state.cust_name = ""
if 'cust_phone' not in st.session_state:
    st.session_state.cust_phone = ""

# --- KẾT NỐI NEON DATABASE ---
# Lệnh này sẽ tự động đọc đường link mật khẩu từ phần "Secrets" trên Streamlit Cloud
conn = st.connection("postgresql", type="sql")

# --- GIAO DIỆN CHÍNH ---
st.title("🏭 Cổng Đặt Hàng Wanchi")
tab1, tab2 = st.tabs(["📦 Danh sách sản phẩm", "🛒 Giỏ hàng & Chốt đơn"])

# ==========================================
# TAB 1: DANH SÁCH SẢN PHẨM
# ==========================================
with tab1:
    try:
        # Lấy dữ liệu từ bảng products trên Neon
        df_products = conn.query("SELECT * FROM products ORDER BY id", ttl=0)
        
        if df_products.empty:
            st.info("Hiện tại chưa có sản phẩm nào trong kho. Vui lòng vào trang Admin để thêm.")
        else:
            cols = st.columns(3)
            for i, row in df_products.iterrows():
                with cols[i % 3]:
                    with st.container(border=True):
                        # Hiển thị ảnh (nếu đã lưu dạng mã Base64)
                        if pd.notna(row['image_data']) and str(row['image_data']).strip() != "":
                            st.image(f"data:image/png;base64,{row['image_data']}", use_container_width=True)
                            
                        st.subheader(row['name'])
                        st.write(f"Mã: {row['product_code']} | KT: {row['size']}")
                        
                        price = row['price'] if pd.notna(row['price']) else 0
                        st.write(f"Giá: **{int(price):,} đ**")
                        
                        with st.expander("Chi tiết"):
                            st.write(row['description'] if pd.notna(row['description']) else '')
                        
                        qty = st.number_input("Số lượng", min_value=1, value=100, step=10, key=f"qty_{row['id']}")
                        if st.button("🛒 Thêm vào giỏ", key=f"add_{row['id']}"):
                            code = row['product_code']
                            st.session_state.cart[code] = st.session_state.cart.get(code, 0) + qty
                            st.toast("✅ Đã thêm vào giỏ hàng!")
    except Exception as e:
        st.error(f"Lỗi kết nối CSDL Neon. Vui lòng kiểm tra lại cấu hình mật khẩu: {e}")

# ==========================================
# TAB 2: GIỎ HÀNG & CHỐT ĐƠN
# ==========================================
with tab2:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("📋 Thông tin người mua")
        st.session_state.cust_name = st.text_input("Tên người mua", st.session_state.cust_name)
        st.session_state.cust_phone = st.text_input("Số điện thoại", st.session_state.cust_phone)
        
        if not st.session_state.cust_name or not st.session_state.cust_phone:
            st.warning("⚠️ Vui lòng điền tên và SĐT để có thể chốt đơn tải PDF.")
    
    with col2:
        st.subheader("🛒 Chi tiết đơn hàng")
        if not st.session_state.cart:
            st.info("Giỏ hàng của bạn đang trống.")
        else:
            total_price = 0
            cart_list = []
            
            for code, qty in st.session_state.cart.items():
                prod_match = df_products[df_products['product_code'] == code]
                if not prod_match.empty:
                    prod = prod_match.iloc[0]
                    price = prod['price'] if pd.notna(prod['price']) else 0
                    
                    line_total = int(price) * qty
                    total_price += line_total
                    
                    cart_list.append({"Mã": code, "Tên": prod['name'], "SL": qty, "Tiền": line_total})
                    st.write(f"- **{prod['name']}** (SL: {qty}) : {line_total:,} đ")
            
            st.write(f"### Tổng cộng: {total_price:,} đ")
            
           # --- KHU VỰC CHỌN CÁCH LƯU ĐƠN HÀNG ---
            if st.session_state.cust_name and st.session_state.cust_phone:
                st.divider()
                st.subheader("🎉 Chọn định dạng để lưu đơn hàng:")
                
                col_pdf, col_img = st.columns(2)
                
                # ==========================================
                # LỰA CHỌN 1: TẠO VÀ TẢI FILE PDF
                # ==========================================
                pdf = FPDF()
                pdf.add_page()
                try:
                    pdf.add_font("Arial", style="", fname="arial.ttf")
                except: pass
                
                try:
                    # Đổi "logo.png" thành tên file logo thực tế của bạn trên Github (vd: logo.jpg)
                    pdf.image("logo.png", x=10, y=10, w=45) 
                except:
                    pdf.set_font("Arial", size=18)
                    pdf.cell(45, 10, txt="WANCHI", ln=False, align="L")
                    
                pdf.set_font("Arial", size=10)
                pdf.set_xy(65, 12)
                pdf.cell(0, 5, txt="775 Võ Hữu Lợi, Xã Lê Minh Xuân, Huyện Bình Chánh, TP.HCM", ln=True)
                pdf.set_xy(65, 18)
                pdf.cell(0, 5, txt="SĐT: 0902.580.828 - 0937.572.577", ln=True)
                pdf.ln(15)
                
                pdf.set_font("Arial", size=18)
                pdf.cell(0, 10, txt="PHIẾU ĐẶT HÀNG", ln=True, align="C")
                pdf.set_font("Arial", size=11)
                pdf.cell(0, 6, txt=f"Ngày: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align="C")
                pdf.ln(8)
                
                pdf.set_font("Arial", size=11)
                pdf.cell(0, 6, txt=f"Khách hàng: {st.session_state.cust_name.upper()}", ln=True)
                pdf.cell(0, 6, txt=f"Điện thoại: {st.session_state.cust_phone}", ln=True)
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
                
                with col_pdf:
                    st.download_button(
                        label="📄 Lưu file PDF", 
                        data=pdf_bytes, 
                        file_name=f"Phieu_Wanchi_{st.session_state.cust_name}.pdf", 
                        mime="application/pdf",
                        use_container_width=True
                    )

                # ==========================================
                # LỰA CHỌN 2: TẠO VÀ TẢI FILE HÌNH ẢNH (JPG)
                # ==========================================
                # Tính toán chiều cao ảnh dựa trên số lượng sản phẩm
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
                    # Đổi "logo.png" thành tên file logo thực tế của bạn
                    logo = Image.open("logo.png").convert("RGBA")
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
                
                with col_img:
                    st.download_button(
                        label="🖼️ Lưu Ảnh đơn hàng (.jpg)", 
                        data=img_bytes, 
                        file_name=f"Phieu_Wanchi_{st.session_state.cust_name}.jpg", 
                        mime="image/jpeg",
                        use_container_width=True
                    )
                    
                    # --- PHẦN 1: HEADER (LOGO & ĐỊA CHỈ) ---
                    # Chèn Logo (Nếu có file logo.png trên GitHub)
                    try:
                        pdf.image("logo.jpg", x=10, y=10, w=45)
                    except:
                        # Nếu không tìm thấy ảnh, in tạm chữ WANCHI
                        pdf.set_font("Arial", size=18)
                        pdf.cell(45, 10, txt="WANCHI", ln=False, align="L")
                        
                    # In Địa chỉ & SĐT bên phải logo
                    pdf.set_font("Arial", size=10)
                    pdf.set_xy(65, 12)
                    pdf.cell(0, 5, txt="775 Võ Hữu Lợi, Xã Lê Minh Xuân, Huyện Bình Chánh, TP.HCM", ln=True)
                    pdf.set_xy(65, 18)
                    pdf.cell(0, 5, txt="SĐT: 0902.580.828 - 0937.572.577", ln=True)
                    
                    pdf.ln(15) # Xuống dòng
                    
                    # --- PHẦN 2: TIÊU ĐỀ & NGÀY THÁNG ---
                    pdf.set_font("Arial", size=18)
                    pdf.cell(0, 10, txt="PHIẾU ĐẶT HÀNG", ln=True, align="C")
                    
                    pdf.set_font("Arial", size=11)
                    ngay_hien_tai = datetime.now().strftime("%d/%m/%Y")
                    pdf.cell(0, 6, txt=f"Ngày: {ngay_hien_tai}", ln=True, align="C")
                    
                    pdf.ln(8)
                    
                    # --- PHẦN 3: THÔNG TIN KHÁCH HÀNG ---
                    pdf.set_font("Arial", size=11)
                    pdf.cell(0, 6, txt=f"Khách hàng: {st.session_state.cust_name.upper()}", ln=True)
                    pdf.cell(0, 6, txt=f"Điện thoại: {st.session_state.cust_phone}", ln=True)
                    
                    pdf.ln(5)
                    
                    # --- PHẦN 4: BẢNG SẢN PHẨM ---
                    # Cài đặt màu nền xám nhạt cho dòng tiêu đề bảng
                    pdf.set_fill_color(230, 230, 230)
                    pdf.set_font("Arial", size=10)
                    
                    # Vẽ dòng tiêu đề (Header)
                    pdf.cell(15, 8, txt="STT", border=1, align="C", fill=True)
                    pdf.cell(85, 8, txt="Tên Sản Phẩm", border=1, align="C", fill=True)
                    pdf.cell(15, 8, txt="SL", border=1, align="C", fill=True)
                    pdf.cell(35, 8, txt="Đơn Giá", border=1, align="C", fill=True)
                    pdf.cell(40, 8, txt="Thành Tiền", border=1, align="C", fill=True)
                    pdf.ln()
                    
                    # Vẽ các dòng dữ liệu sản phẩm
                    for i, item in enumerate(cart_list, 1):
                        pdf.cell(15, 8, txt=str(i), border=1, align="C")
                        pdf.cell(85, 8, txt=item['Tên'], border=1)
                        pdf.cell(15, 8, txt=str(item['SL']), border=1, align="C")
                        
                        # Định dạng tiền tệ có dấu chấm (VD: 12.187.000)
                        don_gia = int(item['Tiền'] / item['SL'])
                        chuoi_don_gia = f"{don_gia:,}".replace(",", ".")
                        chuoi_thanh_tien = f"{item['Tiền']:,}".replace(",", ".")
                        
                        pdf.cell(35, 8, txt=chuoi_don_gia, border=1, align="R")
                        pdf.cell(40, 8, txt=chuoi_thanh_tien, border=1, align="R")
                        pdf.ln()
                        
                    # Dòng TỔNG CỘNG cuối bảng
                    pdf.cell(150, 8, txt="TỔNG CỘNG:", border=1, align="R")
                    chuoi_tong_cong = f"{total_price:,}".replace(",", ".")
                    pdf.cell(40, 8, txt=chuoi_tong_cong, border=1, align="R")
                    
                    # --- XUẤT FILE ---
                    pdf_bytes = bytes(pdf.output())
                    
                    st.success("Tạo đơn hàng thành công! Nhấn nút bên dưới để tải file.")
                    st.download_button(
                        label="⬇️ TẢI FILE PDF ĐƠN HÀNG VỀ MÁY", 
                        data=pdf_bytes, 
                        file_name=f"DonHang_Wanchi_{st.session_state.cust_name}.pdf", 
                        mime="application/pdf"
                    )
