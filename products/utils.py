def get_breadcrumbs(folder, product):
    # Initialize with the root breadcrumb
    breadcrumbs = [{'id': product.id, 'name': product.product_name, 'is_root': True}]
    if folder.is_root:
        return breadcrumbs

    # Get ancestors including the current folder
    ancestors = folder.get_ancestors(include_self=True)
    for ancestor in ancestors:
        if ancestor.is_root:
            continue  # Skip root since it's already added
        breadcrumbs.append({'id': ancestor.id, 'name': ancestor.name, 'is_root': False})

    return breadcrumbs