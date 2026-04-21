import streamlit as st
import pandas as pd
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
        df_products = conn.query("SELECT * FROM products ORDER BY id")
        
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
            
            # --- XỬ LÝ NÚT BẤM VÀ XUẤT PDF ---
            if st.session_state.cust_name and st.session_state.cust_phone:
                if st.button("📄 Chốt đơn & Tải file PDF", type="primary"):
                    
                    pdf = FPDF()
                    pdf.add_page()
                    
                    try:
                        pdf.add_font("Arial", style="", fname="arial.ttf")
                    except Exception as e:
                        st.error("Lỗi: Không tìm thấy file font 'arial.ttf' trên máy chủ.")
                    
                    # --- PHẦN 1: HEADER (LOGO & ĐỊA CHỈ) ---
                    # Chèn Logo (Nếu có file logo.png trên GitHub)
                    try:
                        pdf.image("logo.jpeg", x=10, y=10, w=45)
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
