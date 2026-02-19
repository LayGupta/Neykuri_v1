import streamlit as st
import tensorflow as tf
import numpy as np
from PIL import Image
import cv2
import base64
from io import BytesIO
import os

# This suppresses the technical "walls of text" in your terminal
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 

def Image_to_base64(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return encoded

@st.cache_resource
def load_my_model():
    # Safe load: compile=False prevents the 'DTypePolicy' and 'Config' errors
    return tf.keras.models.load_model("neykuri_model_v1.keras", compile=False)

model = load_my_model()

class_names = ['Kabam', 'Pithakabam', 'Pithalipitham', 'Pitham', 'Pithavatham']
class_descriptions = {
    "Kabam": "Coldness/heaviness; respiratory or metabolism issues.",
    "Pithakabam": "Mixed fire and mucus; inflammation or indigestion.",
    "Pithalipitham": "Excess bile/acidity; skin rashes or irritability.",
    "Pitham": "Bile-dominant; heat-related disorders and ulcers.",
    "Pithavatham": "Bile and wind; nervousness or fluctuating energy."
}

st.set_page_config(page_title="Neykuri Classifier", layout="wide")

st.markdown("""
    <style>
        .title { font-size: 40px; text-align: center; color: #2E4053; }
        .pred-card { background-color: #ffffff; padding: 20px; border-radius: 15px; border: 1px solid #EAECEE; text-align: center; }
        .prediction-text { font-size: 20px; font-weight: bold; color: #1D8348; margin-top: 10px; }
        .confidence-text { font-size: 16px; color: #566573; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">Neykuri Pattern Classifier</div>', unsafe_allow_html=True)
uploaded_files = st.file_uploader("Upload Neikuri Images", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

def process_and_predict(pil_img):
    # 1. Standardize size
    img = pil_img.convert("RGB").resize((224, 224))
    img_array = np.array(img, dtype=np.float32)
    img_array = np.expand_dims(img_array, axis=0)
    
    # 2. Prediction
    preds = model.predict(img_array, verbose=0) # verbose=0 keeps terminal clean
    score = np.max(preds)
    class_idx = np.argmax(preds)
    
    return class_names[class_idx], score, img

if uploaded_files:
    cols = st.columns(len(uploaded_files))
    for i, file in enumerate(uploaded_files):
        img_input = Image.open(file)
        label, confidence, processed_img = process_and_predict(img_input)
        
        with cols[i]:
            st.markdown('<div class="pred-card">', unsafe_allow_html=True)
            st.image(processed_img, use_container_width=True)
            st.markdown(f'<div class="prediction-text">{label}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="confidence-text">Confidence: {confidence:.1%}</div>', unsafe_allow_html=True)
            st.write(f"*{class_descriptions[label]}*")
            st.markdown('</div>', unsafe_allow_html=True)