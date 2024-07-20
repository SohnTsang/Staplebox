from django.templatetags.static import static

def get_file_type_icon(file_name):
    extension = file_name.split('.')[-1].lower()
    icon_map = {
        'png': static("images/table_icon/png.png"),
        'csv': static("images/table_icon/csv.png"),
        'zip': static("images/table_icon/zip.png"),
        'jpg': static("images/table_icon/jpg.png"),
        'pdf': static("images/table_icon/pdf.png"),
        'doc': static("images/table_icon/doc.png"),
        'docx': static("images/table_icon/doc.png"),
        'xls': static("images/table_icon/xls.png"),
        'xlsx': static("images/table_icon/xls.png"),
        'ppt': static("images/table_icon/ppt.png"),
        'txt': static("images/table_icon/txt.png"),
        'default': static("images/table_icon/file.png"),
    }
    return icon_map.get(extension, icon_map['default'])
