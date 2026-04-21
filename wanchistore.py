import streamlit as st
import pandas as pd
from fpdf import FPDF
from sqlalchemy import text

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
                    
                    # Khởi tạo PDF
                    pdf = FPDF()
                    pdf.add_page()
                    
                    # Nạp Font Arial (bắt buộc có file arial.ttf trên GitHub)
                    try:
                        pdf.add_font("Arial", style="", fname="arial.ttf")
                        pdf.set_font("Arial", size=12)
                    except Exception as e:
                        st.error("Lỗi: Không tìm thấy file font 'arial.ttf' trên máy chủ.")
                    
                    # Ghi thông tin
                    pdf.cell(200, 10, txt="PHIEU DAT HANG - WANCHI PLASTIC", ln=True, align="C")
                    pdf.cell(200, 10, txt=f"Khách hàng: {st.session_state.cust_name} - SĐT: {st.session_state.cust_phone}", ln=True)
                    pdf.ln(5)
                    
                    # In danh sách sản phẩm
                    for item in cart_list:
                        pdf.cell(200, 10, txt=f"Mã: {item['Mã']} | {item['Tên']} | SL: {item['SL']} | Thành tiền: {item['Tiền']:,} đ", ln=True)
                    
                    pdf.ln(5)
                    pdf.set_font("Arial", style="", size=14)
                    pdf.cell(200, 10, txt=f"TỔNG CỘNG: {total_price:,} VNĐ", ln=True)
                    
                    # Xuất PDF ra trình duyệt
                    pdf_bytes = bytes(pdf.output())
                    
                    st.success("Tạo đơn hàng thành công! Nhấn nút bên dưới để tải file.")
                    st.download_button(
                        label="⬇️ TẢI FILE PDF ĐƠN HÀNG VỀ MÁY", 
                        data=pdf_bytes, 
                        file_name=f"DonHang_Wanchi_{st.session_state.cust_name}.pdf", 
                        mime="application/pdf"
                    )
