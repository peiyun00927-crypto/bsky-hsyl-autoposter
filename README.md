# Bluesky Daily Auto-Poster for HSYL Kitchen Equipment

针对 **宏盛元利商用厨房设备 (www.hsylkitchen.com)** 的 Bluesky (`bsky.app`) 自动化营销发帖系统。

旨在实现两大核心价值：
1. **外链与 SEO 沉淀**：自动生成带缩略图的高点击率卡片外链（OpenGraph External Card）及正文超链接 Facets，提升 Google 等搜索引擎收录与反向链接权重。
2. **专业 B2B 品牌营销**：针对酒店、中央厨房、学校/企业食堂、餐饮连锁及工程设计顾问，按技术选型、HACCP 合规标准、动线设计方案、重型商用设备四大维度轮播，杜绝低质垃圾群发，塑造权威商用厨具制造商形象。

---

## 目录结构

```
bsky-hsyl-autoposter/
├── bsky_poster.py          # 主执行脚本：登录、上传缩略图 Blob、构建 Facet、发帖与历史归档
├── content_engine.py       # 内容引擎：Sitemap 爬虫、页面 OG 元数据提取、智能营销文案与字节切片
├── post_queue.json         # 精选高转化选题库（包含痛点 Hook、价值 Insight、精准 Hashtag）
├── posted_history.json     # 发帖历史存档（记录已发 URL、时间与 Bluesky Post URI，避免重复）
├── config.py               # 环境变量与配置参数解析
├── requirements.txt        # Python 依赖清单 (requests, beautifulsoup4, python-dotenv)
├── run_daily.sh            # 本地/Cron 一键调度包装脚本
├── .env.example            # 账号与环境变量模版
└── .github/workflows/
    └── daily_post.yml      # GitHub Actions 免费免开机云端每日定时工作流
```

---

## 快速上手

### 1. 安装依赖
```bash
cd /Users/haixin/.gemini/antigravity/scratch/bsky-hsyl-autoposter
pip install -r requirements.txt
```

### 2. 模拟运行测试 (无需账号密码)
在不连接真实 Bluesky 账号的情况下，完整测试爬虫抓取、文案生成、字符数校验与卡片元数据：
```bash
python3 bsky_poster.py --dry-run
```
或者指定官网任意页面进行测试：
```bash
python3 bsky_poster.py --dry-run --force-url "https://www.hsylkitchen.com/materials-fabrication/304-vs-316-stainless-steel-for-commercial-kitchens.html"
```

---

## 配置真实发帖账号

### 第一步：获取 Bluesky App Password（应用专用密码）
为了保护账号安全，**请勿使用主密码**，推荐使用官方 App Password：
1. 登录 [bsky.app](https://bsky.app)
2. 进入 **Settings (设置)** -> **Privacy and security (隐私与安全)** -> **App passwords (应用密码)**
3. 点击 **Add App Password**，输入名称（如 `hsyl-poster`），复制生成的形如 `xxxx-xxxx-xxxx-xxxx` 的密码。

### 第二步：创建 `.env` 文件
```bash
cp .env.example .env
```
用编辑器打开 `.env` 填入配置：
```ini
BSKY_HANDLE=yourname.bsky.social
BSKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

### 第三步：真实发帖测试
```bash
python3 bsky_poster.py
```
发帖成功后，终端会打印出帖子的公共访问链接（如 `https://bsky.app/profile/.../post/...`）。

---

## 定时任务设置（三种方式任选其一）

### 方案 A：GitHub Actions 免开机云端定时（强烈推荐 ⭐⭐⭐⭐⭐）
**优势**：100% 免费、无需保持电脑开机、定时精准、自动备份发帖历史。
1. 将此文件夹内容推送到你的 GitHub 私有仓库（Private Repo）。
2. 在 GitHub 仓库页面进入 **Settings** ➔ **Secrets and variables** ➔ **Actions**。
3. 添加两个 Repository secrets：
   - `BSKY_HANDLE`: 你的 Bluesky Handle
   - `BSKY_APP_PASSWORD`: 你的 Bluesky App Password
4. 仓库内自带的 `.github/workflows/daily_post.yml` 会在每天 UTC 02:00（北京时间 10:00）自动执行并发帖。

### 方案 B：Mac 本地定时任务 (crontab)
如果希望在本地运行，可以使用系统自带的 cron：
1. 打开终端输入：
   ```bash
   crontab -e
   ```
2. 添加以下一行（例如每天上午 10:00 自动执行）：
   ```cron
   0 10 * * * /Users/haixin/.gemini/antigravity/scratch/bsky-hsyl-autoposter/run_daily.sh >> /Users/haixin/.gemini/antigravity/scratch/bsky-hsyl-autoposter/cron.log 2>&1
   ```

### 方案 C：Python 后台守护进程模式
如果你有一台常开的 VPS 或服务器，可以直接以后台进程方式启动：
```bash
nohup python3 bsky_poster.py --daemon --interval-hours 24 > autoposter.log 2>&1 &
```
