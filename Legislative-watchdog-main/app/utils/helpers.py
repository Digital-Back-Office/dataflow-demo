# import re


# def clean_text(text: str) -> str:
#     """
#     Basic text cleaning utility.
#     Removes null chars and excessive whitespace.
#     """
#     if not text:
#         return ""

#     text = text.replace("\x00", "")
#     text = re.sub(r"\s+", " ", text)
#     return text.strip()


# def safe_filename(name: str) -> str:
#     """
#     Convert string into safe file name.
#     """
#     if not name:
#         return "file"

#     name = "".join(c for c in name if c.isalnum() or c in (" ", "_"))
#     return name.strip().replace(" ", "_")