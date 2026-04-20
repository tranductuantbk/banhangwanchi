import streamlit as st
import pandas as pd
import base64
from fpdf import FPDF
from io import BytesIO
from sqlalchemy import text

# 1. Cấu hình & Kết nối
st.set_page_config(page_title="Wanchi Plastic - Hệ thống đặt hàng", layout="wide")
conn = st.connection("postgresql", type="sql")

# Khởi tạo giỏ hàng
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

# Hàm xử lý ảnh sang chuỗi để lưu DB
def image_to_base64(uploaded_file):
    if uploaded_file is not None:
        return base64.b64encode(uploaded_file.getvalue()).decode()
    return None

# --- ĐIỀU HƯỚNG ---
st.sidebar.title("MENU WANCHI")
page = st.sidebar.radio("Chọn trang:", ["Danh mục sản phẩm", "Giỏ hàng", "Quản trị Admin"])

# ---------------------------------------------------------
# TRANG 1: QUẢN TRỊ ADMIN (LOGIN & NHẬP SP)
# ---------------------------------------------------------
if page == "Quản trị Admin":
    st.header("🔐 Khu vực dành cho Quản trị viên")
    
    if not st.session_state.is_admin:
        with st.form("login_form"):
            user = st.text_input("Tên đăng nhập")
            pw = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("Đăng nhập"):
                if user == st.secrets["admin"]["username"] and pw == st.secrets["admin"]["password"]:
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    st.error("Sai tài khoản hoặc mật khẩu!")
    else:
        st.success("Chào Di Linh! Bạn đang ở quyền Admin.")
        if st.button("Đăng xuất"):
            st.session_state.is_admin = False
            st.rerun()

        st.subheader("➕ Thêm sản phẩm mới")
        with st.form("add_product", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                m_code = st.text_input("Mã sản phẩm (Mã SP)")
                m_name = st.text_input("Tên sản phẩm")
                m_size = st.text_input("Kích thước")
            with col2:
                m_price = st.number_input("Giá (VNĐ)", min_value=0)
                m_img = st.file_uploader("Tải ảnh sản phẩm", type=['png', 'jpg', 'jpeg'])
            
            m_desc = st.text_area("Thông tin chi tiết sản phẩm")
            
            if st.form_submit_button("Lưu vào hệ thống"):
                img_base64 = image_to_base64(m_img)
                query = text("INSERT INTO products (product_code, name, size, description, price, image_data) VALUES (:c, :n, :s, :d, :p, :i)")
                with conn.session as session:
                    session.execute(query, {"c": m_code, "n": m_name, "s": m_size, "d": m_desc, "p": m_price, "i": img_base64})
                    session.commit()
                st.success(f"Đã thêm sản phẩm {m_name} thành công!")

# ---------------------------------------------------------
# TRANG 2: DANH MỤC SẢN PHẨM (XEM & CHỌN MUA)
# ---------------------------------------------------------
elif page == "Danh mục sản phẩm":
    st.header("📦 Danh mục sản phẩm Wanchi")
    
    # Lấy dữ liệu từ Neon
    data = conn.query("SELECT * FROM products")
    
    if data.empty:
        st.info("Hiện chưa có sản phẩm nào trong kho.")
    else:
        # Hiển thị dạng lưới
        for i in range(0, len(data), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(data):
                    row = data.iloc[i + j]
                    with cols[j]:
                        with st.container(border=True):
                            if row['image_data']:
                                st.image(f"data:image/png;base64,{row['image_data']}", use_container_width=True)
                            st.subheader(row['name'])
                            st.write(f"**Mã SP:** {row['product_code']}")
                            st.write(f"**Kích thước:** {row['size']}")
                            st.write(f"**Giá:** {row['price']:,} VNĐ")
                            
                            with st.expander("Chi tiết sản phẩm"):
                                st.write(row['description'])
                            
                            qty = st.number_input("Số lượng", min_value=1, value=1, key=f"qty_{row['id']}")
                            if st.button("🛒 Thêm vào giỏ", key=f"btn_{row['id']}"):
                                item = {
                                    "id": row['id'],
                                    "name": row['name'],
                                    "code": row['product_code'],
                                    "price": row['price'],
                                    "qty": qty
                                }
                                st.session_state.cart.append(item)
                                st.toast(f"Đã thêm {qty} {row['name']} vào giỏ hàng")

# ---------------------------------------------------------
# TRANG 3: GIỎ HÀNG & XUẤT PDF
# ---------------------------------------------------------
elif page == "Giỏ hàng":
    st.header("🛒 Giỏ hàng của bạn")
    
    if not st.session_state.cart:
        st.warning("Giỏ hàng đang trống. Vui lòng quay lại chọn sản phẩm.")
    else:
        df_cart = pd.DataFrame(st.session_state.cart)
        st.table(df_cart[['code', 'name', 'qty', 'price']])
        
        total = (df_cart['qty'] * df_cart['price']).sum()
        st.subheader(f"Tổng giá trị dự kiến: {total:,} VNĐ")

        if st.button("🗑️ Làm trống giỏ hàng"):
            st.session_state.cart = []
            st.rerun()

        st.divider()
        st.write("Sau khi kiểm tra đúng mẫu mã và số lượng, hãy xuất file PDF và gửi cho chúng tôi qua Zalo.")
        
        # Logic xuất PDF đơn giản
        if st.button("📄 Chốt đơn & Xuất file PDF"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt="PHIEU DAT HANG - WANCHI PLASTIC", ln=True, align='C')
            pdf.ln(10)
            
            for item in st.session_state.cart:
                line = f"- {item['name']} ({item['code']}): {item['qty']} cai"
                pdf.cell(200, 10, txt=line, ln=True)
            
            pdf.ln(5)
            pdf.cell(200, 10, txt=f"TONG CONG: {total:,} VND", ln=True)
            
            # Gửi file về trình duyệt
            pdf_output = pdf.output(dest='S').encode('latin1')
            st.download_button("Tải file PDF về máy", data=pdf_output, file_name="Don_Hang_Wanchi.pdf")