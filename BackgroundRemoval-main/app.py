from PIL import Image, ImageOps
import streamlit as st
import numpy as np
from io import BytesIO
import base64
import os
import traceback
import time
from rembg import remove 

try:
    from streamlit_image_comparison import image_comparison
except Exception:
    image_comparison = None

SEO_TITLE = "Image Background Remover | Remove Photo Background Online"
SEO_DESCRIPTION = "Upload an image, remove its background instantly, and download transparent or solid-background outputs in PNG, JPG, WEBP, or SVG."

st.set_page_config(layout="wide", page_title=SEO_TITLE)
st.header("Image Background Remover")
st.text(SEO_DESCRIPTION)

st.markdown(
    """
    <style>
      .hero-wrap {
          padding: 0.2rem 0 1rem 0;
      }
      .hero-title {
          font-size: 2rem;
          font-weight: 700;
          letter-spacing: -0.02em;
          margin-bottom: 0.2rem;
      }
      .hero-subtitle {
          color: #6b7280;
          font-size: 1rem;
          margin-bottom: 0.75rem;
      }
      .meta-card {
          border: 1px solid rgba(120, 120, 120, 0.2);
          border-radius: 12px;
          padding: 0.9rem;
          background: rgba(125,125,125,0.04);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero-wrap">
      <div class="hero-title">Background Remover</div>
      <div class="hero-subtitle">Upload a photo, remove the background, and export in your preferred format.</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.write("## Controls ⚙️")

# Increased file size limit
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
AUTO_MAX_SIDE = 2000  # internal safety resize

# Download the fixed image
def convert_image(img, output_format="PNG", jpg_background="#FFFFFF"):
    buf = BytesIO()
    format_upper = output_format.upper()

    if format_upper == "SVG":
        png_buf = BytesIO()
        rgba = img.convert("RGBA")
        rgba.save(png_buf, format="PNG")
        b64_png = base64.b64encode(png_buf.getvalue()).decode("utf-8")
        w, h = rgba.size
        svg_text = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<image href="data:image/png;base64,{b64_png}" width="{w}" height="{h}"/></svg>'
        )
        return svg_text.encode("utf-8")

    if format_upper in {"JPG", "JPEG"}:
        rgb = tuple(int(jpg_background[i : i + 2], 16) for i in (1, 3, 5))
        base = Image.new("RGB", img.size, rgb)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        base.paste(img, mask=img.split()[-1])
        base.save(buf, format="JPEG", quality=95, optimize=True)
        return buf.getvalue()

    if format_upper == "WEBP":
        # Keep alpha if present; quality tuned for visual balance
        img.save(buf, format="WEBP", quality=95, method=6)
    else:
        img.save(buf, format="PNG")

    byte_im = buf.getvalue()
    return byte_im


def human_size(bytes_value):
    units = ["B", "KB", "MB", "GB"]
    size = float(bytes_value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024


def apply_background_color(foreground, hex_color):
    """Composite transparent image onto a solid background color."""
    if foreground.mode != "RGBA":
        foreground = foreground.convert("RGBA")

    rgb = tuple(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    bg = Image.new("RGBA", foreground.size, rgb + (255,))
    bg.alpha_composite(foreground)
    return bg

# Resize image while maintaining aspect ratio
def resize_image(image, max_size):
    if max_size is None:
        return image

    width, height = image.size
    if width <= max_size and height <= max_size:
        return image
    
    if width > height:
        new_width = max_size
        new_height = int(height * (max_size / width))
    else:
        new_height = max_size
        new_width = int(width * (max_size / height))
    
    return image.resize((new_width, new_height), Image.LANCZOS)

@st.cache_data
def process_image(image_bytes):
    """Process image with caching to avoid redundant processing"""
    try:
        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)

        # Resize large images to prevent memory issues
        resized = resize_image(image, AUTO_MAX_SIDE)

        # Process the image
        fixed = remove(resized)

        # Ensure predictable output type
        if not isinstance(fixed, Image.Image):
            fixed = Image.fromarray(np.array(fixed))

        return image, resized, fixed
    except Exception as e:
        st.error(f"Error processing image: {str(e)}")
    return None, None, None


def fix_image(upload, output_format, bg_mode, bg_color, download_slot):
    try:
        start_time = time.time()
        progress_bar = st.sidebar.progress(0)
        status_text = st.sidebar.empty()
        
        status_text.text("Loading image...")
        progress_bar.progress(10)
        
        # Read image bytes
        if isinstance(upload, str):
            # Default image path
            if not os.path.exists(upload):
                st.error(f"Default image not found at path: {upload}")
                return
            with open(upload, "rb") as f:
                image_bytes = f.read()
            source_name = os.path.basename(upload)
        else:
            # Uploaded file
            image_bytes = upload.getvalue()
            source_name = upload.name
        
        status_text.text("Processing image...")
        progress_bar.progress(30)
        
        # Process image (using cache if available)
        image, resized, fixed = process_image(image_bytes)
        if image is None or resized is None or fixed is None:
            return

        if bg_mode == "Solid color":
            fixed = apply_background_color(fixed, bg_color)
        
        progress_bar.progress(80)
        status_text.text("Rendering preview...")

        # Metadata
        with st.container(border=True):
            st.markdown("### Image details")
            m1, m2, m3 = st.columns(3)
            m1.markdown(
                f"<div class='meta-card'><strong>Original</strong><br>{image.width} × {image.height}px</div>",
                unsafe_allow_html=True,
            )
            m2.markdown(
                f"<div class='meta-card'><strong>Processed</strong><br>{fixed.width} × {fixed.height}px</div>",
                unsafe_allow_html=True,
            )
            m3.markdown(
                f"<div class='meta-card'><strong>File size</strong><br>{human_size(len(image_bytes))}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("### Preview")

        # Prepare RGB versions for slider component compatibility
        original_preview = resized.convert("RGB")
        fixed_preview = fixed.convert("RGB") if fixed.mode != "RGB" else fixed
        
        if image_comparison is not None:
            image_comparison(
                img1=original_preview,
                img2=fixed_preview,
                label1="Before",
                label2="After",
                width=860,
                starting_position=50,
                show_labels=True,
                make_responsive=True,
                in_memory=True,
            )
        else:
            st.info("Interactive slider unavailable (optional dependency missing). Showing processed preview only.")
            st.image(fixed_preview, use_container_width=True)
        
        # Prepare download button
        fmt = output_format.upper()
        ext = "jpg" if fmt in {"JPG", "JPEG"} else fmt.lower()
        mime = {
            "PNG": "image/png",
            "JPG": "image/jpeg",
            "JPEG": "image/jpeg",
            "WEBP": "image/webp",
            "SVG": "image/svg+xml",
        }.get(fmt, "image/png")

        if fmt in {"JPG", "JPEG"} and bg_mode == "Transparent":
            st.toast("ℹ️ JPG does not support transparency; white background will be used.", icon="🖼️")

        download_name = f"{os.path.splitext(source_name)[0]}_nobg.{ext}"

        download_slot.download_button(
            "Download",
            convert_image(fixed, output_format, jpg_background=bg_color),
            download_name,
            mime,
            use_container_width=True,
        )
        
        progress_bar.progress(100)
        processing_time = time.time() - start_time
        status_text.text(f"Done in {processing_time:.2f}s")
        st.toast(f"✅ Processing complete in {processing_time:.2f}s", icon="🎉")
        
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.sidebar.error("Failed to process image")
        st.toast("❌ Failed to process image", icon="⚠️")
        # Log the full error for debugging
        print(f"Error in fix_image: {traceback.format_exc()}")

# Sidebar controls
my_upload = st.sidebar.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])
bg_mode = st.sidebar.radio("Background", ["Transparent", "Solid color"], index=0)
bg_color = st.sidebar.color_picker("Solid background color", "#FFFFFF", disabled=bg_mode != "Solid color")

download_row = st.sidebar.container()
fmt_col, dl_col = download_row.columns([1.35, 1], vertical_alignment="bottom")
output_format = fmt_col.selectbox("Download as", ["PNG", "JPG", "WEBP", "SVG"], index=0)
dl_col.markdown("<div style='height: 1.85rem;'></div>", unsafe_allow_html=True)
download_slot = dl_col.empty()

# Information about limitations
with st.sidebar.expander("ℹ️ Image Guidelines"):
    st.write("""
    - Maximum file size: 10MB
    - Very large images are automatically resized for stable processing
    - Download formats: PNG, JPG, WEBP, SVG
    - Processing time depends on image size
    """)

# Process the image
if my_upload is not None:
    if my_upload.size > MAX_FILE_SIZE:
        msg = f"The uploaded file is too large. Please upload an image smaller than {MAX_FILE_SIZE/1024/1024:.1f}MB."
        st.error(msg)
        st.toast(msg, icon="📦")
    else:
        fix_image(
            upload=my_upload,
            output_format=output_format,
            bg_mode=bg_mode,
            bg_color=bg_color,
            download_slot=download_slot,
        )
else:
    # Try default images in order of preference
    default_images = ["./zebra.jpg", "./wallaby.png"]
    for img_path in default_images:
        if os.path.exists(img_path):
            fix_image(
                upload=img_path,
                output_format=output_format,
                bg_mode=bg_mode,
                bg_color=bg_color,
                download_slot=download_slot,
            )
            break
    else:
        st.info("Upload an image to get started.")
