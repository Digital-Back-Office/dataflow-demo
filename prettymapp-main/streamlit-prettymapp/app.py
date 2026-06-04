import copy
import json
import sys

import streamlit as st
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from osmnx._errors import InsufficientResponseError
except Exception:
    InsufficientResponseError = None

# Optional interactive map picker (streamlit-folium + folium). If not installed,
# we'll show a helpful message when the user selects the picker mode.
try:
    from streamlit_folium import st_folium
    import folium
    _HAS_ST_FOLIUM = True
except Exception:
    _HAS_ST_FOLIUM = False

from utils import (
    st_get_osm_geometries,
    st_plot_all,
    get_colors_from_style,
    plt_to_svg,
    slugify,
)
from prettymapp.geo import GeoCodingError, get_aoi
from prettymapp.settings import STYLES

SEO_TITLE = "Prettymapp | Generate Beautiful OpenStreetMap Posters"
SEO_DESCRIPTION = "Create stylish city maps from OpenStreetMap data with custom themes, radius, shapes, and export options like PNG, SVG, and GeoJSON."

st.set_page_config(
    page_title=SEO_TITLE, page_icon="🖼️", initial_sidebar_state="collapsed"
)
st.header("Prettymapp")
st.text(SEO_DESCRIPTION)
st.markdown("# Prettymapp")
st.markdown(
    """
    <style>
    .pm-toolbar-note {
        margin-top: 0.35rem;
        color: #4b5563;
        font-size: 0.9rem;
    }
    .pm-chip {
        display: inline-block;
        border: 1px solid rgba(120, 120, 120, 0.25);
        border-radius: 999px;
        padding: 0.2rem 0.65rem;
        font-size: 0.85rem;
        color: #334155;
        background: rgba(120, 120, 120, 0.06);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with (_HERE / "examples.json").open("r", encoding="utf8") as f:
    EXAMPLES = json.load(f)

if not st.session_state:
    st.session_state.update(EXAMPLES["Macau"])

    lc_class_colors = get_colors_from_style("Peach")
    st.session_state.lc_classes = list(lc_class_colors.keys())  # type: ignore
    st.session_state.update(lc_class_colors)
    st.session_state["previous_style"] = "Peach"

st.session_state.setdefault("show_map_picker", False)
st.session_state.setdefault("picked_lat", None)
st.session_state.setdefault("picked_lon", None)
st.session_state.setdefault("name_on", False)

example_image_pattern = str(_HERE / "example_prints" / "{}_small.png")
example_image_fp = [
    example_image_pattern.format(name.lower()) for name in list(EXAMPLES.keys())[:4]
]
example_names = list(EXAMPLES.keys())[:4]
example_cols = st.columns(4)
for col, image_fp, name in zip(example_cols, example_image_fp, example_names):
    with col:
        col.image(image_fp, use_container_width=True)
        col.caption(name)

st.write("")

toolbar_left, toolbar_right = st.columns([1.2, 3.8])
if toolbar_left.button("📍 Pick from map", use_container_width=True):
    st.session_state["show_map_picker"] = not st.session_state["show_map_picker"]

if st.session_state.get("picked_lat") is not None and st.session_state.get("picked_lon") is not None:
    toolbar_right.markdown(
        f"<span class='pm-chip'>Selected: {float(st.session_state['picked_lat']):.6f}, {float(st.session_state['picked_lon']):.6f}</span>",
        unsafe_allow_html=True,
    )
else:
    toolbar_right.markdown(
        "<div class='pm-toolbar-note'>Tip: enter an address, or click <strong>Pick from map</strong> to choose a precise pin location.</div>",
        unsafe_allow_html=True,
    )

if st.session_state["show_map_picker"]:
    if not _HAS_ST_FOLIUM:
        st.warning(
            "Interactive map picker requires `streamlit-folium` and `folium`. "
            "Install them and restart the app."
        )
    else:
        st.caption("How to drop a pin: click once on the map to place the pin. Click another spot to move it.")
        m = folium.Map(
            location=[20.0, 0.0],
            zoom_start=2,
            tiles="OpenStreetMap",
        )

        if st.session_state.get("picked_lat") is not None and st.session_state.get("picked_lon") is not None:
            folium.Marker(
                [float(st.session_state["picked_lat"]), float(st.session_state["picked_lon"])],
                tooltip="Selected location",
            ).add_to(m)

        map_data = st_folium(
            m,
            width="100%",
            height=430,
            returned_objects=["last_clicked"],
        )

        # Handle click — only pin placement
        if map_data:
            if map_data.get("last_clicked"):
                clicked = map_data["last_clicked"]
                try:
                    new_lat = float(clicked["lat"])
                    new_lon = float(clicked["lng"])
                    st.session_state["picked_lat"] = new_lat
                    st.session_state["picked_lon"] = new_lon
                except Exception:
                    pass

        if st.session_state.get("picked_lat") is not None and st.session_state.get("picked_lon") is not None:
            st.caption(
                f"Pinned location: {float(st.session_state['picked_lat']):.6f}, {float(st.session_state['picked_lon']):.6f}"
            )

form = st.form(key="form_settings")
col1, col2, col3 = form.columns([3, 1, 1])

if st.session_state["show_map_picker"]:
    address = st.session_state.get("address", "")
else:
    address = col1.text_input(
        "Location address",
        key="address",
        help="Optional if you already picked a point on the map.",
    )

radius = col2.slider(
    "Radius (meter)",
    100,
    1500,
    key="radius",
)

style: str = col3.selectbox(
    "Color theme",
    options=list(STYLES.keys()),
    key="style",
)

expander = form.expander("Customize map style")
col1style, col2style, _, col3style = expander.columns([2, 2, 0.1, 1])

shape_options = ["circle", "rectangle"]
shape = col1style.radio(
    "Map Shape",
    options=shape_options,
    key="shape",
)

bg_shape_options = ["rectangle", "circle", None]
bg_shape = col1style.radio(
    "Background Shape",
    options=bg_shape_options,
    key="bg_shape",
)
bg_color = col1style.color_picker(
    "Background Color",
    key="bg_color",
)
bg_buffer = col1style.slider(
    "Background Size",
    min_value=0,
    max_value=50,
    help="How much the background extends beyond the figure.",
    key="bg_buffer",
)

col1style.markdown("---")
contour_color = col1style.color_picker(
    "Map contour color",
    key="contour_color",
)
contour_width = col1style.slider(
    "Map contour width",
    0,
    30,
    help="Thickness of contour line sourrounding the map.",
    key="contour_width",
)

name_on = col2style.checkbox(
    "Display title",
    help="If checked, adds the selected address as the title. Can be customized below.",
    key="name_on",
)
custom_title = col2style.text_input(
    "Custom title (optional)",
    max_chars=30,
    key="custom_title",
)
font_size = col2style.slider(
    "Title font size",
    min_value=1,
    max_value=50,
    key="font_size",
)
font_color = col2style.color_picker(
    "Title font color",
    key="font_color",
)
text_x = col2style.slider(
    "Title left/right",
    -100,
    100,
    key="text_x",
)
text_y = col2style.slider(
    "Title top/bottom",
    -100,
    100,
    key="text_y",
)
text_rotation = col2style.slider(
    "Title rotation",
    -90,
    90,
    key="text_rotation",
)

if style != st.session_state["previous_style"]:
    st.session_state.update(get_colors_from_style(style))  # type: ignore
draw_settings = copy.deepcopy(STYLES[style])
for lc_class in st.session_state.lc_classes:
    picked_color = col3style.color_picker(lc_class, key=lc_class)
    if "_" in lc_class:
        lc_class, idx = lc_class.split("_")
        draw_settings[lc_class]["cmap"][int(idx)] = picked_color  # type: ignore
    else:
        draw_settings[lc_class]["fc"] = picked_color

submit_generate = form.form_submit_button(label="Generate map", use_container_width=True)

generated = False
df = None
config = None
fig = None
input_type = "Address"
fname_base = "prettymapp"

if submit_generate:
    picked_lat_raw = st.session_state.get("picked_lat")
    picked_lon_raw = st.session_state.get("picked_lon")
    address_raw = st.session_state.get("address", "")
    address_clean = str(address_raw).strip()
    has_picked_point = picked_lat_raw is not None and picked_lon_raw is not None

    with st.spinner("Creating map... (may take up to a minute)"):
        rectangular = shape != "circle"
        try:
            if has_picked_point:
                input_type = "Pick on map"
                picked_lat = float(picked_lat_raw)
                picked_lon = float(picked_lon_raw)
                aoi = get_aoi(
                    coordinates=(picked_lat, picked_lon),
                    radius=radius,
                    rectangular=rectangular,
                )
                fname_base = f"{picked_lat:.6f}_{picked_lon:.6f}"
                default_name = f"{picked_lat:.5f}, {picked_lon:.5f}"
            elif address_clean:
                input_type = "Address"
                aoi = get_aoi(address=address_clean, radius=radius, rectangular=rectangular)
                fname_base = slugify(address_clean)
                default_name = address_clean
            else:
                st.error(
                    "No location provided. To drop a pin: click 📍 Pick from map, then click once on the map to place a pin, and click Generate map again."
                )
                aoi = None

            if aoi is not None:
                df = st_get_osm_geometries(aoi=aoi)
                config = {
                    "aoi_bounds": aoi.bounds,
                    "draw_settings": draw_settings,
                    "name_on": name_on,
                    "name": default_name if custom_title == "" else custom_title,
                    "font_size": font_size,
                    "font_color": font_color,
                    "text_x": text_x,
                    "text_y": text_y,
                    "text_rotation": text_rotation,
                    "shape": shape,
                    "contour_width": contour_width,
                    "contour_color": contour_color,
                    "bg_shape": bg_shape,
                    "bg_buffer": bg_buffer,
                    "bg_color": bg_color,
                }
                fig = st_plot_all(_df=df, **config)
                st.pyplot(fig, pad_inches=0, bbox_inches="tight", transparent=True, dpi=300)
                generated = True
        except GeoCodingError as e:
            st.error(f"ERROR: {str(e)}")
        except Exception as e:
            if InsufficientResponseError is not None and isinstance(e, InsufficientResponseError):
                st.error(
                    "No matching OpenStreetMap features were found for this area. "
                    "Try moving to a denser location or increasing the radius."
                )
            elif type(e).__name__ == "InsufficientResponseError":
                st.error(
                    "No matching OpenStreetMap features were found for this area. "
                    "Try moving to a denser location or increasing the radius."
                )
            else:
                raise

if generated:
    st.markdown("</br>", unsafe_allow_html=True)
    st.markdown("</br>", unsafe_allow_html=True)

    with st.expander("Export image"):
        img_format = st.selectbox(
            "File type",
            options=["png", "svg"],
            index=0,
            help="Export the rendered map in different formats.",
            key="export_image_format",
            format_func=lambda v: "PNG (300 dpi)" if v == "png" else "SVG (lossless)",
        )
        mime_by_format = {
            "png": "image/png",
            "svg": "image/svg+xml",
        }

        def _make_download_data():
            if img_format == "svg":
                return plt_to_svg(fig)

            import io

            buf = io.BytesIO()
            savefig_kwargs = dict(
                format=img_format,
                pad_inches=0,
                bbox_inches="tight",
                transparent=True,
            )
            if img_format == "png":
                savefig_kwargs["dpi"] = 300
            fig.savefig(buf, **savefig_kwargs)
            buf.seek(0)
            return buf.getvalue()

        st.download_button(
            label="Download",
            data=_make_download_data(),
            file_name=f"{fname_base}.{img_format}",
            mime=mime_by_format[img_format],
            on_click="ignore",
            key=f"download_image_{img_format}",
        )

    ex1, ex2 = st.columns(2)

    with ex1.expander("Export geometries as GeoJSON"):
        st.write(f"{df.shape[0]} geometries")
        st.download_button(
            label="Download",
            data=df.to_json().encode("utf-8"),
            file_name=f"{fname_base}.geojson",
            mime="application/geo+json",
        )

    export_config = {
        "input_type": input_type,
        "address": address if input_type == "Address" else None,
        "coordinates": (
            (float(st.session_state["picked_lat"]), float(st.session_state["picked_lon"]))
            if input_type == "Pick on map"
            and st.session_state.get("picked_lat") is not None
            and st.session_state.get("picked_lon") is not None
            else None
        ),
        **config,
    }
    with ex2.expander("Export map configuration"):
        st.write(export_config)
else:
    st.info("Set a location and click **Generate map** to render and unlock exports.")

st.session_state["previous_style"] = style