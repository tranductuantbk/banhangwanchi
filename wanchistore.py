import streamlit as st
import pandas as pd
from fpdf import FPDF

st.set_page_config(page_title="Bán Hàng Wanchi", layout="wide")

# Khởi tạo Giỏ hàng trong bộ nhớ tạm
if 'cart' not in st.session_state:
    st.session_state.cart = {}
if 'cust_name' not in st.session_state:
    st.session_state.cust_name = ""
if 'cust_phone' not in st.session_state:
    st.session_state.cust_phone = ""

# --- KẾT NỐI GOOGLE SHEETS ---
# NHỚ THAY CHUỖI ID BÊN DƯỚI BẰNG ID GOOGLE SHEET CỦA BẠN NHÉ
SHEET_ID = "thay-bang-ID-google-sheet-cua-ban" 
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data(ttl=60) # Cập nhật dữ liệu mỗi 60 giây
def load_data():
    return pd.read_csv(CSV_URL)

try:
    df_products = load_data()
except Exception as e:
    st.error("Chưa kết nối được Google Sheet. Vui lòng kiểm tra lại ID và quyền chia sẻ file.")
    df_products = pd.DataFrame()

# --- GIAO DIỆN CHÍNH ---
st.title("🏭 Cổng Đặt Hàng Wanchi")
tab1, tab2 = st.tabs(["📦 Danh sách sản phẩm", "🛒 Giỏ hàng & Chốt đơn"])

# ==========================================
# TAB 1: DANH SÁCH SẢN PHẨM
# ==========================================
with tab1:
    if not df_products.empty:
        cols = st.columns(3)
        for i, row in df_products.iterrows():
            with cols[i % 3]:
                with st.container(border=True):
                    # Kiểm tra xem có điền Link Ảnh trong Excel không
                    if pd.notna(row.get('Link Ảnh')) and str(row.get('Link Ảnh')).strip() != "":
                        st.image(row['Link Ảnh'])
                        
                    st.subheader(row.get('Tên SP', 'Sản phẩm chưa có tên'))
                    st.write(f"Mã: {row.get('Mã SP', '')} | KT: {row.get('Kích thước', '')}")
                    
                    # Lấy giá, nếu rỗng thì để số 0
                    price = row.get('Giá', 0)
                    if pd.isna(price):
                        price = 0
                    st.write(f"Giá: **{int(price):,} đ**")
                    
                    with st.expander("Chi tiết"):
                        st.write(row.get('Mô tả', ''))
                    
                    qty = st.number_input("Số lượng", min_value=1, value=100, step=10, key=f"qty_{i}")
                    if st.button("🛒 Thêm vào giỏ", key=f"add_{i}"):
                        code = row.get('Mã SP')
                        if code:
                            st.session_state.cart[code] = st.session_state.cart.get(code, 0) + qty
                            st.toast("✅ Đã thêm vào giỏ hàng!")

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
            st.warning("⚠️ Vui lòng điền tên và SĐT để có thể tải file PDF.")
    
    with col2:
        st.subheader("🛒 Chi tiết đơn hàng")
        if not st.session_state.cart:
            st.info("Giỏ hàng của bạn đang trống.")
        else:
            total_price = 0
            cart_list = []
            
            for code, qty in st.session_state.cart.items():
                prod_match = df_products[df_products['Mã SP'] == code]
                if not prod_match.empty:
                    prod = prod_match.iloc[0]
                    price = prod.get('Giá', 0)
                    if pd.isna(price): price = 0
                    
                    line_total = int(price) * qty
                    total_price += line_total
                    
                    cart_list.append({"Mã": code, "Tên": prod.get('Tên SP', ''), "SL": qty, "Tiền": line_total})
                    st.write(f"- **{prod.get('Tên SP', '')}** (SL: {qty}) : {line_total:,} đ")
            
            st.write(f"### Tổng cộng: {total_price:,} đ")
            
            # --- XỬ LÝ NÚT BẤM VÀ XUẤT PDF (ĐÃ CHỈNH LỀ CHUẨN) ---
            if st.session_state.cust_name and st.session_state.cust_phone:
                if st.button("📄 Chốt đơn & Tải file PDF", type="primary"):
                    
                    # Khởi tạo PDF
                    pdf = FPDF()
                    pdf.add_page()
                    
                    # Gọi Font Arial để không lỗi tiếng Việt (BẮT BUỘC có file arial.ttf trên GitHub)
                    try:
                        pdf.add_font("Arial", style="", fname="arial.ttf")
                        pdf.set_font("Arial", size=12)
                    except Exception as e:
                        st.error("Lỗi Font chữ: Vui lòng đảm bảo bạn đã tải file 'arial.ttf' lên GitHub.")
                    
                    # Ghi thông tin
                    pdf.cell(200, 10, txt="PHIEU DAT HANG - WANCHI PLASTIC", ln=True, align="C")
                    pdf.cell(200, 10, txt=f"Khách hàng: {st.session_state.cust_name} - SĐT: {st.session_state.cust_phone}", ln=True)
                    pdf.ln(5) # Cách dòng
                    
                    # In danh sách sản phẩm
                    for item in cart_list:
                        pdf.cell(200, 10, txt=f"Mã: {item['Mã']} | {item['Tên']} | SL: {item['SL']} | Thành tiền: {item['Tiền']:,} đ", ln=True)
                    
                    pdf.ln(5)
                    pdf.set_font("Arial", style="", size=14)
                    pdf.cell(200, 10, txt=f"TỔNG CỘNG: {total_price:,} VNĐ", ln=True)
                    
                    # Xuất PDF ra trình duyệt
                    pdf_bytes = pdf.output(dest='S').encode('latin1')
                    
                    st.success("Tạo đơn hàng thành công! Nhấn nút bên dưới để tải file.")
                    st.download_button(
                        label="⬇️ TẢI FILE PDF ĐƠN HÀNG VỀ MÁY", 
                        data=pdf_bytes, 
                        file_name=f"DonHang_Wanchi_{st.session_state.cust_name}.pdf", 
                        mime="application/pdf"
                    )
