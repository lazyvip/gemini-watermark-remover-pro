<p align="center">
  <img alt="Gemini Watermark Remover Pro" src="docs/demo/image_clean_demo.png" width="260"/>
</p>

<h1 align="center">Gemini Watermark Remover Pro</h1>

<p align="center">
  <b>Google Gemini / Veo 图片 & 视频 一键无痕去水印</b><br/>
  纯代数反向 Alpha 混合逆解，无损还原底层纹理，零模糊、零涂抹
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white"/>
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green.svg"/>
  <img alt="Platform" src="https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-lightgrey"/>
  <img alt="OpenCV" src="https://img.shields.io/badge/OpenCV-4.8%2B-5C3EE8"/>
</p>

<p align="center">
  <a href="#演示效果">演示效果</a> ·
  <a href="#核心原理">核心原理</a> ·
  <a href="#快速上手">快速上手</a> ·
  <a href="#使用教程">使用教程</a> ·
  <a href="#命令行参数">命令行参数</a>
</p>

---

## ✨ 简介

使用 Google Gemini / Veo 生成图片或视频时，右下角总会被加上一个半透明的 **四角星品牌水印**。常规工具（剪映、Photoshop 涂抹、AI 重绘）要么破坏画质，要么产生毛玻璃糊斑。

本项目用**数学精确还原**的方式替代"盲目修补"——通过反向 Alpha 混合逐像素把水印下方的真实纹理"提"回来，做到 **100% 保留底层细节、零模糊**。

- ✅ 同时支持 **图片**（PNG/JPG/WEBP/…）和 **视频**（MP4）
- ✅ 单像素纯代数逆解，**无 Inpaint 漫水**，杜绝糊斑
- ✅ 视频可选 **Lanczos4 超分至 1080P** 并保留原音轨
- ✅ **零配置**：自动补全 FFmpeg，Windows 拖拽即用
- ✅ 可作 **Trae/Claude Skill** 挂载，交给 AI 自动执行

> 本项目是 [lazyvip/gemini-watermark-remover](https://github.com/lazyvip/gemini-watermark-remover)（纯图片版）的强化超集，新增了视频引擎、自动档位匹配、透明通道保留与跨平台自动封装能力。

---

## 🎬 演示效果

一张对比图感受一下：左侧为带水印原图，右侧为去水印后的结果。

![图片去水印对比](docs/demo/image_watermark_compare.png)

返回局部放大区域可以看到，渐变背景在去水印后**完全连续**，没有任何残留星形、色差或模糊边界——这正是纯代数还原和 Inpaint 涂抹的本质区别。

---

## 🔬 核心原理

### 水印是怎么"盖"上去的

Gemini 采用经典的 **Alpha 加权混合（alpha compositing）** 把白色四角星叠加到画面上：

$$I_{\text{watermarked}} = \alpha \cdot 255 + (1 - \alpha) \cdot I_{\text{original}}$$

- $\alpha$ 是每个像素的透明白度（`0.0` 全透明 ～ `1.0` 不透明），来自 Google 官方的 48×48 Alpha Map
- `255` 是白色本次所用的 `LOGO_VALUE`

### 反向"解"出水印下面的原图

既然我们**精确知道**每个像素的 $\alpha$，就可以直接代数求逆：

$$I_{\text{original}} = \frac{I_{\text{watermarked}} - \alpha \cdot 255}{1 - \alpha}$$

这是一个**单像素、点对点**的纯数学运算，完全不需要借用周围像素的颜色（那是 `cv2.inpaint` 干的事）。因此水印下方原本的木纹、衣服褶皱、物体反光和细微噪点都能 100% 原样保留。

### 工程上的三个关键细节

1. **底噪门限截断**：设 `ALPHA_NOISE_FLOOR = 3/255`，对外围透明的微小 Alpha 信号直接归零，避免在边缘形成暗圈。
2. **增益适配（图片 vs 视频）**：
   - 图片没有 H.264/YUV420 色彩损耗，用 `gain = 1.0`（与官方 `blendModes.js` 图片引擎一致），无损精确还原；
   - 视频经过有损压缩，色度有轻微衰减，用 `gain = 0.58` 补偿，平衡"中心残白"与"边缘暗环"。
3. **水印尺寸档位自动匹配**（图片）：依据官方尺寸目录，最大边 ≥1600px 匹配 96px 水印 + 64px 边距，其余匹配 48px + 32px。

> 💡 对比：Inpaint 属于"无中生有"的邻域漫水填补，必然抹平高频纹理；本项目属于"数学提纯"，完全靠该像素自身残留的光子信号还原，因此能做到图片级无痕。

---

## 🚀 快速上手

### 环境要求

- Python 3.8+
- FFmpeg（**无需手动安装**：脚本会自动从官方源静默补全）

```bash
pip install -r requirements.txt
```

### 图片去水印

```bash
python remove_watermark.py "gemini_image.png"
# → 输出 gemini_image_clean.png
```

### 视频去水印（默认超分至 1080P）

```bash
python remove_watermark.py "gemini_video.mp4"
# → 输出 gemini_video_clean.mp4
```

---

## 📖 使用教程

### Windows 用户（零配置，最推荐）

1. 安装 [Python 3.8+](https://www.python.org/downloads/) 并勾选 **Add Python to PATH**；
2. 把要处理的 **图片或视频文件直接拖拽到 `run_windows.bat` 图标上**；
3. 脚本自动检测文件类型、自动补齐依赖，生成纯净成品。

### 命令行进阶

```bash
# 视频保持原分辨率（不做超分）
python remove_watermark.py "video.mp4" --no-upscale

# 指定输出路径
python remove_watermark.py "img.png" -o out.png

# 手动指定图片水印尺寸/边距（自动档位不适用时）
python remove_watermark.py "img.png" --logo-size 96 --margin 64

# 切换去水印模式（默认 lossless 最佳）
python remove_watermark.py "video.mp4" --mode hybrid
```

### 作为 Trae / Claude Skill 使用

将本目录整体复制到对应 Skill 目录：

- macOS: `~/.trae-cn/skills/gemini-watermark-remover-pro/`
- Windows: `%USERPROFILE%\.trae-cn\skills\gemini-watermark-remover-pro\`

然后在 Trae 中对话：*"帮我去掉这个 Gemini 图片/视频的水印"*，AI 会自动调度执行。

---

## ⚙️ 命令行参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `input` | 输入文件路径（图片或视频） | 必填 |
| `-o, --output` | 输出文件路径 | 自动生成 `_clean` |
| `--mode` | 去水印模式：`lossless` / `hybrid` / `inpaint` | `lossless` |
| `--gain` | Alpha 增益：视频 0.58，图片 1.0 | 自动识别 |
| `--no-upscale` | （视频）不做 1080P 超分 | 关闭 |
| `--logo-size` | （图片）水印像素尺寸 | 0=自动 |
| `--margin` | （图片）水印距右下角边距 | 0=自动 |

---

## ❓ 常见问题

<details>
<summary>为什么我的图片去水印后有残留？</summary>

多半是水印尺寸档位与该图片不符。Gemini 的不同生成尺寸使用了 48px 或 96px 的水印，自动匹配基于官方档位。若仍不精确，用 `--logo-size 96 --margin 64` 或 `--logo-size 48 --margin 32` 手动指定。
</details>

<details>
<summary>视频去水印后画质会下降吗？</summary>

不会。画面采用纯代数还原（不二次压缩像素），超分用 Lanczos4 高保真插值，封装用 CRF=18 高质量编码并保留原始 AAC 音轨。全程尽量保持源质量。
</details>

<details>
<summary>运行提示找不到 FFmpeg？</summary>

脚本内置自动下载逻辑，通常会在联网时静默补全。若离线环境失败，可用 `pip install imageio-ffmpeg` 安装一个附带 FFmpeg 的备选方案。
</details>

---

## 📄 许可 & 致谢

- 开源许可：[MIT](./LICENSE)
- Alpha Map 与尺寸档位源自开源技术剖析
- 前端/信息展示参考：[ai.lazyso.com](https://ai.lazyso.com)

如果你觉得这个工具帮到了你，欢迎 ⭐ Star、Fork、Issue，或在评论区分享你的使用体验。

<p align="center">Made with ❤️ for the Gemini creator community</p>