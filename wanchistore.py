import streamlit as st
import pandas as pd
from fpdf import FPDF
from sqlalchemy import text

st.set_page_config(page_title="Wanchi Plastic - Mua hàng", layout="wide")

# Kết nối DB và khởi tạo Giỏ hàng
conn = st.connection("postgresql", type="sql")
if 'cart' not in st.session_state:
    st.session_state.cart = {}
if 'cust_name' not in st.session_state:
    st.session_state.cust_name = ""
if 'cust_phone' not in st.session_state:
    st.session_state.cust_phone = ""

st.title("🏭 Cổng Đặt Hàng Wanchi")
tab1, tab2 = st.tabs(["📦 Danh sách sản phẩm", "🛒 Giỏ hàng & Chốt đơn"])

# --- TAB DANH SÁCH SẢN PHẨM ---
with tab1:
    try:
        df_products = conn.query("SELECT * FROM products ORDER BY id")
        if df_products.empty:
            st.info("Hiện chưa có sản phẩm.")
        else:
            cols = st.columns(3)
            for i, row in df_products.iterrows():
                with cols[i % 3]:
                    with st.container(border=True):
                        if pd.notna(row['image_data']) and row['image_data'] != "":
                            st.image(f"data:image/png;base64,{row['image_data']}")
                        st.subheader(row['name'])
                        st.write(f"Mã: {row['product_code']} | KT: {row['size']}")
                        st.write(f"Giá: **{row['price']:,} đ**")
                        with st.expander("Chi tiết"):
                            st.write(row['description'])
                        
                        qty = st.number_input("Số lượng", min_value=1, value=100, step=10, key=f"qty_{row['id']}")
                        if st.button("🛒 Thêm vào giỏ", key=f"add_{row['id']}"):
                            st.session_state.cart[row['id']] = st.session_state.cart.get(row['id'], 0) + qty
                            st.toast("Đã thêm vào giỏ hàng!")
    except Exception as e:
        st.error("Chưa kết nối được dữ liệu hoặc bảng chưa tồn tại.")

# --- TAB GIỎ HÀNG ---
with tab2:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Thông tin người mua")
        st.session_state.cust_name = st.text_input("Tên người mua", st.session_state.cust_name)
        st.session_state.cust_phone = st.text_input("Số điện thoại", st.session_state.cust_phone)
    
    with col2:
        st.subheader("Chi tiết đơn hàng")
        if not st.session_state.cart:
            st.info("Giỏ hàng trống.")
        else:
            total_price = 0
            cart_list = []
            for pid, qty in st.session_state.cart.items():
                prod = df_products[df_products['id'] == pid].iloc[0]
                line_total = prod['price'] * qty
                total_price += line_total
                cart_list.append({"Mã": prod['product_code'], "Tên": prod['name'], "SL": qty, "Tiền": line_total})
                st.write(f"- {prod['name']} (SL: {qty}) : {line_total:,} đ")
            
            st.write(f"### Tổng cộng: {total_price:,} đ")
            
            if st.session_state.cust_name and st.session_state.cust_phone:
                if st.button("📄 Chốt đơn & Tải file PDF", type="primary"):
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", size=12) # Cần có file arial.ttf trong thư mục để gõ tiếng Việt
                    pdf.cell(200, 10, txt=f"Khach hang: {st.session_state.cust_name} - SDT: {st.session_state.cust_phone}", ln=True)
                    for item in cart_list:
                        pdf.cell(200, 10, txt=f"{item['Mã']} | {item['Tên']} | SL: {item['SL']} | {item['Tiền']:,} d", ln=True)
                    pdf.cell(200, 10, txt=f"TONG TIEN: {total_price:,} d", ln=True)
                    
                    pdf_bytes = pdf.output(dest='S').encode('latin1')
                    st.download_button("⬇️ Nhấn để tải PDF", data=pdf_bytes, file_name="DonHang.pdf", mime="application/pdf")