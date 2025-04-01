from fasthtml.common import (
    Html, Head, Title, Meta, Style, Body, Div, H1, 
    A, Span, Script, respond
)
from starlette.responses import HTMLResponse
from typing import List, Optional, Dict, Any, Union

# Create CSS Dictionary for consistent styling
STYLES = {
    "body": "font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;",
    "container": "border: 1px solid #ddd; border-radius: 5px; padding: 20px; margin-bottom: 20px;",
    "header": "display: flex; justify-content: space-between; align-items: center;",
    "nav": "display: flex; gap: 10px;",
    "nav_link": "text-decoration: none; padding: 8px 12px; background: #f0f0f0; border-radius: 4px;",
    "nav_link_hover": "background: #e0e0e0;",
    "section": "margin-top: 20px;",
    "heading": "margin-top: 0;",
    "empty_state": "padding: 20px; text-align: center; background: #f5f5f5; border-radius: 4px;",
    "button": "display: inline-block; padding: 8px 12px; background: #4CAF50; color: white; text-decoration: none; border: none; border-radius: 4px; cursor: pointer;",
    "button_hover": "background: #45a049;",
    "button_current": "background: #9E9E9E;",
    "badge": "display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold;",
    "badge_success": "background-color: #d4edda; color: #155724;",
    "badge_warning": "background-color: #fff3cd; color: #856404;",
    "form_group": "margin-bottom: 15px;",
    "label": "display: block; margin-bottom: 5px;",
    "input": "width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;",
    "card": "border: 1px solid #ddd; border-radius: 4px; padding: 15px; margin-bottom: 15px;",
    "card_header": "display: flex; justify-content: space-between; margin-bottom: 10px;",
    "card_brand": "font-weight: bold;",
    "table": "width: 100%; border-collapse: collapse; margin-bottom: 20px;",
    "th": "padding: 8px; text-align: left; border-bottom: 1px solid #ddd; background-color: #f5f5f5;",
    "td": "padding: 8px; text-align: left; border-bottom: 1px solid #ddd;",
    "plans": "display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 20px;",
    "plan": "flex: 1; min-width: 200px; border: 1px solid #ddd; border-radius: 4px; padding: 20px;",
    "plan_current": "border-color: #4CAF50; border-width: 2px;",
    "plan_header": "margin-bottom: 15px;",
    "plan_name": "font-size: 1.2em; font-weight: bold;",
    "plan_price": "font-size: 1.5em; font-weight: bold; margin: 10px 0;",
    "plan_price_period": "font-size: 0.7em; color: #666;",
    "plan_features": "margin-bottom: 20px;",
    "plan_action": "margin-top: auto;",
    "customer_info": "background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin-bottom: 20px; border-left: 4px solid #17a2b8;",
    "social_login_section": "margin-top: 20px;",
    "divider": "text-align: center; position: relative; margin: 20px 0;",
    "social_button": "display: block; width: 100%; padding: 10px; margin-bottom: 10px; text-align: center; background: #4285F4; color: white; text-decoration: none; border-radius: 4px;",
}


def fasthtml_layout(title: str, content: Union[str, Any], nav_items: Optional[List[Dict[str, str]]] = None):
    """Creates a base layout with common elements using FastHTML components"""
    if nav_items is None:
        nav_items = [
            {"text": "Home", "href": "/"},
            {"text": "Logout", "href": "/logout"}
        ]
    
    # Create navigation links using FastHTML components
    nav_links = [
        A(item["text"], href=item["href"], style=STYLES["nav_link"])
        for item in nav_items
    ]
    
    # Create CSS rules
    css_rules = [
        f"body {{ {STYLES['body']} }}",
        f".container {{ {STYLES['container']} }}",
        f".header {{ {STYLES['header']} }}",
        f".nav {{ {STYLES['nav']} }}",
        f".nav a:hover {{ {STYLES['nav_link_hover']} }}",
        f".section {{ {STYLES['section']} }}",
        f"h1, h2, h3 {{ {STYLES['heading']} }}",
        f".empty-state {{ {STYLES['empty_state']} }}",
        f".button {{ {STYLES['button']} }}",
        f".button:hover {{ {STYLES['button_hover']} }}",
        f".button.current {{ {STYLES['button_current']} }}",
        f".badge {{ {STYLES['badge']} }}",
        f".badge-success {{ {STYLES['badge_success']} }}",
        f".badge-warning {{ {STYLES['badge_warning']} }}",
        f".form-group {{ {STYLES['form_group']} }}",
        f"label {{ {STYLES['label']} }}",
        f"input[type='text'], input[type='password'], input[type='email'], input[type='number'] {{ {STYLES['input']} }}",
        f".card {{ {STYLES['card']} }}",
        f".card-header {{ {STYLES['card_header']} }}",
        f".card-brand {{ {STYLES['card_brand']} }}",
        f"table {{ {STYLES['table']} }}",
        f"th {{ {STYLES['th']} }}",
        f"td {{ {STYLES['td']} }}",
        f".plans {{ {STYLES['plans']} }}",
        f".plan {{ {STYLES['plan']} }}",
        f".plan.current {{ {STYLES['plan_current']} }}",
        f".plan-header {{ {STYLES['plan_header']} }}",
        f".plan-name {{ {STYLES['plan_name']} }}",
        f".plan-price {{ {STYLES['plan_price']} }}",
        f".plan-price .period {{ {STYLES['plan_price_period']} }}",
        f".plan-features {{ {STYLES['plan_features']} }}",
        f".plan-action {{ {STYLES['plan_action']} }}",
        f".customer-info {{ {STYLES['customer_info']} }}",
        f".social-login-section {{ {STYLES['social_login_section']} }}",
        f".divider {{ {STYLES['divider']} }}",
        f".social-button {{ {STYLES['social_button']} }}",
    ]
    
    # Build the HTML document using FastHTML components
    html_doc = Html(
        Head(
            Title(f"{title} - API Test Client"),
            Meta(charset="UTF-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            Style("\n".join(css_rules))
        ),
        Body(
            Div(
                Div(
                    H1(title),
                    Div(*nav_links, class_="nav"),
                    class_="header"
                ),
                content,
                class_="container"
            )
        )
    )
    
    # Return the rendered HTML
    return  html_doc 