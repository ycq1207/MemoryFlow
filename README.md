# MemoryFlow

一款基于 FSRS-5 算法的通用记忆软件，支持古诗、文章、知识点、单词、公式等内容的间隔重复记忆。

## 特性

- **通用记忆引擎** — 支持古诗、文章、题目、单词、公式等多种内容类型
- **FSRS-5 算法** — 基于艾宾浩斯遗忘曲线的智能间隔重复算法
- **打字验证** — 通过输入内容进行主动回忆，而非简单的"记得/不记得"
- **分段学习** — 长内容自动分段，逐段学习后整体默写
- **提示系统** — 可选的首字提示，使用后需无提示验证
- **错题复习** — 复习错误的内容可重新学习后再次复习
- **深色模式** — 支持浅色/深色主题切换
- **热力图** — 可视化学习记录
- **快速导入** — 通过 UI 快速导入内容

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行应用

```bash
python main.py
```

### 运行测试

```bash
python -m unittest discover -s tests -v
```

## 构建发布版

### 安装构建工具

```bash
pip install pyinstaller
```

### Windows 构建

```bash
# 方法1: 使用构建脚本
build.bat

# 方法2: 手动构建
pyinstaller --onefile --noconsole --name MemoryFlow --clean --collect-submodules app --add-data "poems/*.json;poems" main.py
```

构建完成后，`MemoryFlow.exe` 位于项目根目录。

### 构建产物

```
MemoryFlow/
├── MemoryFlow.exe    # 单文件可执行程序 (~50MB)
└── ...
```

## 支持的内容类型

| 类型 | 说明 | 示例 |
|------|------|------|
| 古诗 | 诗句 + 释义 | 静夜思、望庐山瀑布 |
| 文章 | 段落 + 摘要 | 散文、议论文 |
| 题目 | 问题 + 答案 | 选择题、简答题 |
| 单词 | 单词 + 释义 |英语单词、专业术语 |
| 公式 | 公式 + 说明 | 数学公式、物理公式 |

## 学习流程

### 学习新内容

1. **阅读理解** — 阅读内容及释义/答案
2. **分段背诵** — 逐段打字默写，可选提示
3. **无提示验证** — 使用提示后需无提示再默写一遍
4. **整体默写** — 全部内容完整默写

### 复习

1. **打字默写** — 逐项输入内容，可选提示
2. **结果评估** — 根据正确率自动评分
3. **错题复习** — 错误内容可重新学习后再次复习

## 项目结构

```
MemoryFlow/
├── main.py                    # 入口
├── requirements.txt           # 依赖
├── LICENSE                    # MIT License
├── README.md                  # 说明文档
├── app/
│   ├── config.py              # 配置
│   ├── core/
│   │   ├── database.py        # SQLite 数据库
│   │   ├── scheduler.py       # FSRS-5 调度器
│   │   └── poem_manager.py    # 内容管理
│   ├── models/
│   │   └── poem.py            # 数据模型
│   └── ui/
│       ├── home_window.py     # 主页仪表盘
│       ├── study_window.py    # 学习模式
│       ├── review_window.py   # 复习模式
│       ├── import_window.py   # 内容导入
│       └── settings_window.py # 设置
├── poems/                     # 内容 JSON 文件
├── tests/
│   ├── test_scheduler.py      # FSRS 算法测试
│   ├── test_database.py       # 数据库测试
│   └── test_poem_manager.py   # 内容管理测试
└── database/                  # SQLite 数据库文件
```

## 技术栈

- **Python 3.10+**
- **PySide6** — Qt for Python
- **SQLite** — 本地数据库
- **FSRS-5** — 间隔重复算法

## 算法说明

MemoryFlow 使用 FSRS-5（Free Spaced Repetition Scheduler v5）算法，根据复习表现动态调整下次复习时间：

- **Rating 1 (Again)** — 忘记，缩短间隔
- **Rating 2 (Hard)** — 困难，略微缩短间隔
- **Rating 3 (Good)** — 良好，正常间隔增长
- **Rating 4 (Easy)** — 简单，大幅延长间隔

## 数据格式

内容以 JSON 格式存储在 `poems/` 目录：

```json
{
  "title": "静夜思",
  "author": "李白",
  "dynasty": "唐",
  "card_type": "poem",
  "content": ["床前明月光", "疑是地上霜", "举头望明月", "低头思故乡"],
  "meaning": ["明亮的月光洒在床前", "好像地上泛起了一层霜", "抬头看看天上的明月", "低头不禁思念起家乡"]
}
```

## 贡献

欢迎提交 Issue 和 Pull Request！

## License

MIT License
