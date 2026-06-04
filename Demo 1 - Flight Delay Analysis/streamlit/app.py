import streamlit as st
import streamlit.components.v1 as components
import json
from utils.queries import (
    get_flight_statistics_summary,
    get_airline_performance_stats,
    get_origin_airport_stats,
)

SEO_TITLE = "Flights Dashboard | Flight Delay Analysis"
SEO_DESCRIPTION = "Interactive flight delay dashboard with airline performance, airport statistics, and delay trends for smarter travel insights."
SEO_KEYWORDS = "flight dashboard, flight delays, airline performance, airport statistics, aviation analytics"


def inject_seo_metadata() -> None:
        seo_payload = {
                "title": SEO_TITLE,
                "description": SEO_DESCRIPTION,
                "keywords": SEO_KEYWORDS,
                "robots": "index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1",
                "canonicalPath": "/",
                "ogType": "website",
                "ogImage": "https://app.dataflow.zone/static/images/dataflow-logo-header.svg",
                "twitterCard": "summary_large_image",
        }

        structured_data = {
                "@context": "https://schema.org",
                "@type": "WebApplication",
                "name": "Flights Dashboard",
                "description": SEO_DESCRIPTION,
                "applicationCategory": "TravelApplication",
                "operatingSystem": "Web Browser",
        }

        script = """
        <script>
        (() => {
            const seo = __SEO_PAYLOAD__;
            const jsonLdData = __JSON_LD__;
            const doc = window.parent && window.parent.document ? window.parent.document : document;
            const loc = window.parent && window.parent.location ? window.parent.location : window.location;
            if (!doc || !loc) return;

            const setMeta = (key, value, isProperty = false) => {
                if (!value) return;
                const selector = isProperty ? `meta[property="${key}"]` : `meta[name="${key}"]`;
                let el = doc.querySelector(selector);
                if (!el) {
                    el = doc.createElement("meta");
                    if (isProperty) {
                        el.setAttribute("property", key);
                    } else {
                        el.setAttribute("name", key);
                    }
                    doc.head.appendChild(el);
                }
                el.setAttribute("content", value);
            };

            const canonicalUrl = `${loc.origin}${seo.canonicalPath || loc.pathname}`;
            doc.title = seo.title;

            let canonical = doc.querySelector("link[rel='canonical']");
            if (!canonical) {
                canonical = doc.createElement("link");
                canonical.setAttribute("rel", "canonical");
                doc.head.appendChild(canonical);
            }
            canonical.setAttribute("href", canonicalUrl);

            setMeta("description", seo.description);
            setMeta("keywords", seo.keywords);
            setMeta("robots", seo.robots);
            setMeta("og:title", seo.title, true);
            setMeta("og:description", seo.description, true);
            setMeta("og:type", seo.ogType, true);
            setMeta("og:url", canonicalUrl, true);
            setMeta("og:image", seo.ogImage, true);
            setMeta("twitter:card", seo.twitterCard);
            setMeta("twitter:title", seo.title);
            setMeta("twitter:description", seo.description);
            setMeta("twitter:image", seo.ogImage);

            let ldJson = doc.querySelector("script[data-seo='flight-dashboard-jsonld']");
            if (!ldJson) {
                ldJson = doc.createElement("script");
                ldJson.type = "application/ld+json";
                ldJson.setAttribute("data-seo", "flight-dashboard-jsonld");
                doc.head.appendChild(ldJson);
            }
            ldJson.textContent = JSON.stringify({ ...jsonLdData, url: canonicalUrl });
        })();
        </script>
        """

        script = script.replace("__SEO_PAYLOAD__", json.dumps(seo_payload)).replace("__JSON_LD__", json.dumps(structured_data))
        components.html(script, height=0)


st.set_page_config(page_title=SEO_TITLE, layout="wide")
inject_seo_metadata()

st.header("Flight Delay Analysis Dashboard")
st.text(SEO_DESCRIPTION)
st.title("✈️ Flights Dashboard")
st.markdown("Explore flight delays, airport stats, airline performance, and an ai chatbot to get answers for your quries.")

# --- Summary Stats ---
st.subheader("📊 Quick Summary")

try:
    stats = get_flight_statistics_summary()
    total_flights = sum(row["total_flights"] for row in stats)
    avg_dep_delay = sum(row["avg_departure_delay"] for row in stats) / len(stats)
    avg_arr_delay = sum(row["avg_arrival_delay"] for row in stats) / len(stats)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Flights", f"{total_flights:,}")
    col2.metric("Avg Departure Delay (min)", f"{avg_dep_delay:.2f}")
    col3.metric("Avg Arrival Delay (min)", f"{avg_arr_delay:.2f}")
except Exception as e:
    st.error(f"Failed to load summary: {e}")
