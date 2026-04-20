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

# ================= 2. 核心功能函数 =================
def get_whois_info(domain):
    """获取域名注册信息"""
    try:
        w = whois.whois(domain)
        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
            
        days_active = (datetime.now() - creation_date).days if creation_date else "Unknown"
        
        return {
            "registrar": w.registrar,
            "creation_date": creation_date.strftime("%Y-%m-%d") if creation_date else "Unknown",
            "days_active": days_active,
            "risk_level": "High (注册不足90天)" if isinstance(days_active, int) and days_active < 90 else "Low"
        }
    except Exception as e:
        return {"error": f"Whois查询失败: {str(e)}"}

def scrape_website(url):
    """抓取网站基础信息与文本"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        title = soup.title.string if soup.title else "No Title"
        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc["content"] if meta_desc else "No Description"
        
        # 提取网页纯文本用于风险词匹配
        text_content = soup.get_text(separator=' ', strip=True).lower()
        found_risks = [word for word in RISK_KEYWORDS if word in text_content]
        
        # 抓取所有外部链接 (检测是否有AB站跳转或隐藏网关)
        links = [a['href'] for a in soup.find_all('a', href=True)]
        external_links = [link for link in links if link.startswith('http') and url not in link]
        
        return {
            "title": title,
            "description": description,
            "found_risks": found_risks,
            "external_links_count": len(external_links),
            "sample_links": external_links[:5] # 仅展示前5个外部链接
        }
    except Exception as e:
        return {"error": f"网页抓取失败: {str(e)}"}

# ================= 3. 页面 UI 与逻辑 =================
st.set_page_config(page_title="商户网站风险扫描", layout="wide")
st.title("🛡️ 出海电商独立站 - 风险快速扫描器")
st.markdown("输入商户网址，系统将自动抓取 **域名信息、网页特征** 并匹配 **合规风险词库**。")

url_input = st.text_input("请输入网址 (例如: https://www.shopify.com):")

if st.button("开始扫描"):
    if not url_input.startswith("http"):
        st.warning("请输入包含 http:// 或 https:// 的完整网址。")
    else:
        domain = urllib.parse.urlparse(url_input).netloc
        
        with st.spinner("正在解析域名与网页内容..."):
            whois_data = get_whois_info(domain)
            site_data = scrape_website(url_input)
            
        # --- 结果展示区 ---
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🌐 域名注册信息 (Whois)")
            if "error" in whois_data:
                st.error(whois_data["error"])
            else:
                st.write(f"**注册商:** {whois_data.get('registrar')}")
                st.write(f"**建站时间:** {whois_data.get('creation_date')} (已运行 {whois_data.get('days_active')} 天)")
                
                if whois_data.get("risk_level") == "High (注册不足90天)":
                    st.error("⚠️ 高风险：该域名为近期新注册，可能存在短期跑路风险。")
                else:
                    st.success("✅ 域名注册时间正常")

        with col2:
            st.subheader("📄 网页特征与合规检查")
            if "error" in site_data:
                st.error(site_data["error"])
            else:
                st.write(f"**网站标题:** {site_data.get('title')}")
                st.write(f"**页面描述:** {site_data.get('description')}")
                
                risks = site_data.get("found_risks")
                if risks:
                    st.error(f"⚠️ 发现敏感违禁词: {', '.join(risks)}")
                else:
                    st.success("✅ 未匹配到已知敏感词")
                
                st.write(f"**外部链接数量:** {site_data.get('external_links_count')} (过多可能涉及流量引出或暗网关)")
                with st.expander("查看部分外部链接样本"):
                    for link in site_data.get('sample_links', []):
                        st.write(link)

        st.divider()
        st.subheader("🤖 智能风控 Agent 研判 (扩展接口)")
        st.info("架构提示：此处可将抓取到的 `title`、`description` 和 `text_content` 作为 Prompt Context 传入 OpenAI/Anthropic API，让 AI 判断该网站的实际售卖品类与合规程度。")