import streamlit as st
import requests
from bs4 import BeautifulSoup
import whois
import urllib.parse
from datetime import datetime

# ================= 1. 风险词库配置 =================
RISK_KEYWORDS = [
    "replica", "fake", "1:1", "cbd", "vape", "marijuana", 
    "casino", "betting", "adult", "escort", "weapon", "gun"
]

# 高危内部路径特征
SUSPICIOUS_PATHS = ["/hidden", "/vip", "/replica", "/b-site", "/pay-link", "/secret", "/checkout_b"]

# 高危外部引流域特征 (通常用于私域售假或逃避客诉)
RISKY_EXTERNAL_DOMAINS = ["t.me", "telegram.org", "wa.me", "whatsapp.com", "wechat"]

# ================= 2. 核心功能函数 =================
def get_whois_info(domain):
    """获取域名注册信息"""
    try:
        w = whois.whois(domain)
        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
            
        if creation_date:
            creation_date_naive = creation_date.replace(tzinfo=None)
            days_active = (datetime.now() - creation_date_naive).days
        else:
            days_active = "Unknown"
        
        return {
            "registrar": w.registrar,
            "creation_date": creation_date.strftime("%Y-%m-%d") if creation_date else "Unknown",
            "days_active": days_active,
            "risk_level": "High (注册不足90天)" if isinstance(days_active, int) and days_active < 90 else "Low"
        }
    except Exception as e:
        return {"error": f"Whois查询失败: {str(e)}"}

def scrape_website(url):
    """抓取网站基础信息与下挂风险特征"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 1. 基础信息与违禁词检查
        title = soup.title.string if soup.title else "No Title"
        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc["content"] if meta_desc else "No Description"
        
        text_content = soup.get_text(separator=' ', strip=True).lower()
        found_risks = [word for word in RISK_KEYWORDS if word in text_content]
        
        # --- 新增：下挂风险探测逻辑 ---
        parsed_base_url = urllib.parse.urlparse(url)
        base_domain = parsed_base_url.netloc
        
        # 2. 链接分类探测
        internal_links = []
        external_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            parsed_href = urllib.parse.urlparse(href)
            if not parsed_href.netloc or parsed_href.netloc == base_domain:
                internal_links.append(href)
            else:
                external_links.append(href)
                
        # 3. 探查高危内部暗链
        found_suspicious_paths = list(set([link for link in internal_links if any(p in link.lower() for p in SUSPICIOUS_PATHS)]))
        
        # 4. 探查高危私域引流
        found_risky_outbounds = list(set([link for link in external_links if any(d in link.lower() for d in RISKY_EXTERNAL_DOMAINS)]))
        
        # 5. 探查 Iframe 嵌套 (AB站套用特征)
        iframes = soup.find_all('iframe')
        iframe_srcs = [iframe.get('src', 'Hidden or No Source') for iframe in iframes]
        
        # 6. 探查自动跳转 (重定向劫持)
        meta_redirect = soup.find("meta", attrs={"http-equiv": "refresh"})
        has_redirect = True if meta_redirect else False

        return {
            "title": title,
            "description": description,
            "found_risks": found_risks,
            "external_links_count": len(external_links),
            "suspicious_paths": found_suspicious_paths,
            "risky_outbounds": found_risky_outbounds,
            "iframes_count": len(iframes),
            "iframe_samples": iframe_srcs[:3],
            "has_redirect": has_redirect
        }
    except Exception as e:
        return {"error": f"网页抓取失败: {str(e)}"}

# ================= 3. 页面 UI 与逻辑 =================
st.set_page_config(page_title="商户网站风险扫描", layout="wide")
st.title("🛡️ 出海电商独立站 - 风险快速扫描器")
st.markdown("输入商户网址，系统将自动抓取 **域名信息、网页特征、下挂暗链** 并进行综合研判。")

url_input = st.text_input("请输入网址 (例如: https://www.shopify.com):")

if st.button("开始扫描"):
    if not url_input.startswith("http"):
        st.warning("请输入包含 http:// 或 https:// 的完整网址。")
    else:
        domain = urllib.parse.urlparse(url_input).netloc
        
        with st.spinner("正在解析域名、爬取网页与下挂链接..."):
            whois_data = get_whois_info(domain)
            site_data = scrape_website(url_input)
            
        col1, col2 = st.columns(2)
        
        # 左侧：Whois与基础合规
        with col1:
            st.subheader("🌐 域名与内容合规")
            if "error" in whois_data:
                st.error(whois_data["error"])
            else:
                st.write(f"**建站时间:** {whois_data.get('creation_date')} (已运行 {whois_data.get('days_active')} 天)")
                if whois_data.get("risk_level") == "High (注册不足90天)":
                    st.error("⚠️ 高风险：该域名为近期新注册，存跑路风险。")
                else:
                    st.success("✅ 域名注册时间正常")
            
            st.divider()
            if "error" not in site_data:
                st.write(f"**网站标题:** {site_data.get('title')}")
                risks = site_data.get("found_risks")
                if risks:
                    st.error(f"⚠️ 发现敏感违禁词: {', '.join(risks)}")
                else:
                    st.success("✅ 未匹配到已知敏感文本")

        # 右侧：下挂风险深度核查 (新增模块)
        with col2:
            st.subheader("🕸️ 下挂资源与暗链风险")
            if "error" in site_data:
                st.error(site_data["error"])
            else:
                # 1. 重定向检查
                if site_data.get("has_redirect"):
                    st.error("🚨 发现网页自动重定向 (Meta Refresh)！极可能是 AB 站流量劫持。")
                else:
                    st.success("✅ 无自动重定向特征")
                
                # 2. 内部暗链检查
                paths = site_data.get("suspicious_paths")
                if paths:
                    st.warning(f"⚠️ 发现高危隐藏目录 ({len(paths)}个):")
                    for p in paths:
                        st.code(p)
                else:
                    st.write("✅ 未发现常规高危隐藏目录")
                
                # 3. 私域引流检查
                outbounds = site_data.get("risky_outbounds")
                if outbounds:
                    st.warning(f"⚠️ 发现向高危私域引流 ({len(outbounds)}个):")
                    for o in outbounds:
                        st.code(o)
                        
                # 4. Iframe 嵌套检查
                iframe_count = site_data.get("iframes_count")
                if iframe_count > 0:
                    st.warning(f"🔍 探测到 {iframe_count} 个 iframe 嵌套层 (需排查是否套用支付网关):")
                    for iframe in site_data.get("iframe_samples"):
                        st.write(f"- `{iframe}`")
                else:
                    st.write("✅ 页面无 Iframe 嵌套")