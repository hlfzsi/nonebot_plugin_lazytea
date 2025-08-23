<div align="center">

<a href="https://github.com/hlfzsi/nonebot_plugin_lazytea">
  <img src="https://socialify.git.ci/hlfzsi/nonebot_plugin_lazytea/image?description=1&descriptionEditable=%E2%9C%A8%20%E4%B8%80%E6%AC%BE%E4%B8%BA%20NoneBot2%20%E7%B2%BE%E5%BF%83%E6%89%93%E9%80%A0%E7%9A%84%E6%9C%AC%E5%9C%B0%E5%9B%BE%E5%BD%A2%E5%8C%96%E7%95%8C%E9%9D%A2%20%E2%9C%A8&issues=1&language=1&logo=https%3A%2F%2Fraw.githubusercontent.com%2Fhlfzsi%2Fnonebot_plugin_lazytea%2Fmain%2Fimages%2FREADME%2Fapp.png&name=1&owner=1&pattern=Plus&stargazers=1&theme=Auto" alt="LazyTea" width="640" height="320" />
</a>

_—— 来喝一杯下午茶，享受片刻的宁静与高效？ ——_

[![PyPI](https://img.shields.io/pypi/v/nonebot-plugin-lazytea.svg)](https://pypi.org/project/nonebot-plugin-lazytea)
[![Total Downloads](https://static.pepy.tech/badge/nonebot-plugin-lazytea)](https://pypi-stats.org/packages/nonebot-plugin-lazytea)
[![Weekly Downloads](https://static.pepy.tech/badge/nonebot-plugin-lazytea/week)](https://pypi-stats.org/packages/nonebot-plugin-lazytea)
![Python Version](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)![Free Threading / No GIL](https://img.shields.io/badge/Free%20Threading%20%2F%20No%20GIL-supported-brightgreen.svg)

</div>

随着您的 NoneBot2 插件日益增多，`.env` 文件是否已变得臃肿不堪，管理起来愈发吃力？

**LazyTea** 正是为此而生。它是一款为 [NoneBot2](https://nonebot.dev/) 精心打造的**本地图形化界面 (GUI)**，致力于让您以更直观、更优雅的方式驾驭您的机器人，将繁琐的管理工作化为一杯下午茶般的轻松惬意。

<br>

# 📌 项目关系

为了更好地理解 LazyTea 生态，请注意以下几个项目的区别与联系：


| 项目                                  | 主要职责                                       | 仓库地址                                                                                     |
| :------------------------------------ | :--------------------------------------------- | :------------------------------------------------------------------------------------------- |
| 🔌**nonebot_plugin_lazytea (本项目)** | **NoneBot2 插件**，作为 LazyTea 的后端服务端。 | [nonebot_plugin_lazytea](https://github.com/hlfzsi/nonebot_plugin_lazytea)                   |
| 🍵**LazyTea Client**                  | **独立桌面客户端**，用于连接并管理后端服务。   | [LazyTea-Client](https://github.com/hlfzsi/LazyTea-Client)                                   |
| 🌐**LazyTea Web**                     | **Web管理界面**，提供跨平台的浏览器访问体验。  | [LazyTea-Web](https://github.com/hlfzsi/LazyTea-Web)                                         |
| 📱**LazyTea Mobile**                  | **跨平台移动客户端**，随时随地管理机器人。     | [LazyTea-mobile](https://github.com/hlfzsi/LazyTea-mobile)                                   |
| 🐚**lazytea-shell-extension**         | **命令行扩展**，允许通过聊天消息执行管理命令。 | [lazytea-shell-extension](https://github.com/hlfzsi/nonebot_plugin_lazytea_shell_extension/) |

简单来说，本项目 (`nonebot_plugin_lazytea`) 作为服务端安装在您的机器人上。您可以直接使用它提供的本地 GUI，也可以选择下载独立的 `LazyTea 客户端/服务端` 来进行远程管理。

<br>

# ✨ 优势

在众多管理工具中，LazyTea 凭借其独特的技术架构与用户体验脱颖而出：

### **坚如磐石的稳定性**

* **进程隔离设计**: LazyTea 作为独立的子进程运行，与您的 NoneBot2 主进程严格分离。这意味着，**即使 GUI 界面意外崩溃，您的机器人核心业务也丝毫不受影响**，确保 7x24 小时稳定在线。

### **优雅先进的架构**

* **现代化 UI 框架 (PySide6)**: 借助 Qt 6.x 强大的跨平台能力与出色的渲染性能，LazyTea 得以在 Windows, macOS, Linux 等主流操作系统上流畅运行，为您带来丝滑的操作体验。
* **高度解耦，无限可能**: LazyTea 基于 WebSocket 实现与 NoneBot2 的通信。这不仅为本地 Bot 提供了强大的管理后台，稍加改造甚至可以实现远程遥控。我们的目标是提供一个通用 GUI 方案，任何兼容 `ipc/func_call.py` 接口的框架都能轻松接入。

### **触手可及的便捷**

* **告别混乱配置**: 为每个插件自动生成专属的可视化配置页面，参数修改从未如此直观简单。
* **插件生态尽在掌握**: 一键检查与更新插件，版本、作者、说明等信息聚合展示，让插件管理一目了然。
* **精细灵活的权限管控**: 提供**非侵入式**的 Matcher 级权限控制，无论是黑名单还是白名单，都能轻松配置。
* **高效的话题追踪**: 右键点击任意消息，即可提取关键词并快速检索相关历史讨论，轻松跟进每一个热点。
* **数据驱动决策**: 通过清晰的图表洞察插件调用情况，帮助您了解用户偏好，优化机器人服务。

> **💡 温馨提示:**
>
> * 为了获得最佳性能体验，建议在挂机时将 LazyTea 最小化或停留在“概览”页面，以减少不必要的资源占用。
> * 部分插件可能使用非标准数据格式（如 non-serializable 对象）作为配置项，这可能导致自动保存失效。我们仍在探索最佳的兼容方案。

<br>

# 📱 应用速览


|                   概览页面                   |                   Bot 页面                   |
| :------------------------------------------: | :------------------------------------------: |
|   ![概览](images/README/1753779214444.png)   | ![Bot设置](images/README/1753779501509.png) |
|              **消息与话题追踪**              |              **插件管理与配置**              |
| ![消息页面](images/README/1753779612117.png) | ![插件列表](images/README/1753779698765.png) |

<br>

# 🚀 快速入门

### **1. 系统要求**

_注：Windows 11 系统下部分字体可能显示不全，如遇此问题，欢迎向我们反馈。_


| 配置级别     | 最低要求    | 推荐配置   | 发烧友配置 |
| :----------- | :---------- | :--------- | :--------- |
| **CPU**      | 任意现代CPU | 双核及以上 | i9-14900KS |
| **内存**     | 80 MB       | 100 MB+    | 192 GB     |
| **硬盘空间** | 200 MB      | 300 MB+    | 400 GB+    |

### **2. 安装**

**无需任何额外配置！** 只需一行命令，启动您的机器人，LazyTea 的窗口便会自动随之呈现。

```bash
nb plugin install nonebot_plugin_lazytea
```

<br>

# 🛠️ 开发者指南

我们诚邀各位插件开发者与 LazyTea 联动，共同打造更繁荣的 NoneBot 生态。集成方式的实现细节，您可以参考 LazyTea 项目顶层的 `__init__.py` 文件。

### **插件元数据约定**

为了让您的插件更好地被 LazyTea 展示，请在 `metadata` 的 `extra` 字段中添加以下可选信息：


| 字段名         | 类型   | 说明                                                                                                                |
| :------------- | :----- | :------------------------------------------------------------------------------------------------------------------ |
| `version`      | `str`  | 用于版本检查。请确保插件主页为 GitHub 地址，且版本号与 Git Tag 一致。遵循 PEP 440。                                 |
| `icon_abspath` | `str`  | 插件图标的**绝对路径**。建议使用优化过的小尺寸图片。                                                                |
| `author`       | `str`  | 插件作者的大名。                                                                                                    |
| `pip_name`     | `str`  | 如果插件导入名与 PyPI 包名不同，请在此处填写正确的 PyPI 包名。                                                      |
| `ui_support`   | `bool` | 设置为`True` 以允许 LazyTea 加载您自定义的 UI 页面和相关逻辑。                                                      |
| `html_exists`  | `bool` | 设置为`True`以允许 LazyTea 应用您自定义的 html 页面和相关逻辑。 (若本项设置为`True`,则`ui_support`也应设置为`True`) |

### **自定义UI开发**

#### 方案一：原生APP

您可以为您的插件打造专属配置页面，替代 LazyTea 的自动生成页面。

* **技术栈要求**: 自定义 UI 必须使用 **PySide6**。
* **启用开关**: 必须在元数据中将 `ui_support` 设为 `True`。
* **解耦设计**: 您的插件**无需将 LazyTea 作为强制依赖**。当用户安装 LazyTea 时，UI 会自动加载；反之，您的插件将以无 UI 模式正常运行。
* 优势：高度自定义，性能表现优异，与`LazyTea`无缝集成
* 劣势：仅在本地GUI可用，开发复杂

在您插件包的顶层目录（`__init__.py` 所在目录），创建以下两个文件，LazyTea 将会自动发现并加载它们：

##### `__call__.py`

* **时机**: GUI 加载完成，`__ui__.py` 导入之前。
* **环境**: 主进程，Async Loop。
* **SDK**: `from nonebot_plugin_lazytea.sdk import SDK_nb`
* **描述**: 您可以在此编写与 NoneBot2 主体交互的代码。
* **配置热重载**: 您可以注册一个与插件包**导入名同名**的函数。当配置更新时，LazyTea 会调用此函数，并将最新的配置实例作为唯一参数传入。

##### `__ui__.py`

* **时机**: `__call__.py` 导入完成之后。
* **环境**: GUI 子进程，QEventLoop。
* **SDK**: `from nonebot_plugin_lazytea.ui.sdk import SDK_UI`
* **描述**: 该文件负责 UI 的构建与交互。**严禁包含或依赖 asyncio/nonebot 相关代码**。
* **入口类**: 定义一个名为 `ShowMyPlugin` 的类，继承自 `QWidget`。LazyTea 将自动实例化这个类作为您的插件页面。

##### **注意事项**

1. 为使自动生成的配置页更易懂，建议使用 `Pydantic` 的 `Field(description="...")` 来描述配置项。
2. 若配置项使用了 non-serializable 对象，建议实现 Pydantic 提供的字段序列化与数据转换方法。
3. 为确保权限管理的最佳兼容性，建议您使用标准的 `Rule` 类型或 `alc` 的规则。

#### 方案二：HTML

您可以为您的插件打造专属配置页面，替代 LazyTea 的自动生成页面。

* **技术栈要求**: 自定义 UI 必须使用HTML，若使用外部本地css/js，需要符合规范。
* **启用开关**: 必须在元数据中将 `ui_support` **和** `html_exists` 设为 `True`。
* **解耦设计**: 您的插件**无需将 LazyTea 作为强制依赖**。当用户安装 LazyTea 时，UI 会自动加载；反之，您的插件将以无 UI 模式正常运行。
* 优势：高度自定义，可在 远程桌面端 / Web 使用，开发便捷
* 劣势：需要遵循`LazyTea`定义的标准以保证可用，部分`LazyTea`连携功能可能受限

在您插件包的顶层目录（`__init__.py` 所在目录），创建以下文件，LazyTea 将会自动发现并加载它：

##### `__call__.py`

* **时机**: GUI 加载完成之后。
* **环境**: 主进程，Async Loop。
* **SDK**: `from nonebot_plugin_lazytea.sdk import SDK_nb`
* **描述**: 您可以在此编写与 NoneBot2 主体交互的代码。
* **配置热重载**: 您可以注册一个与插件包**导入名同名**的函数。当配置更新时，LazyTea 会调用此函数，并将最新的配置实例作为唯一参数传入。
* **配置HTML请求处理器**：您可以注册一个与插件包**导入名.html**的函数，这个函数应当是`nonebot_plugin_lazytea.sdk`中的`HTMLFunction`类型，返回值为`PluginHTML`。

##### 关于HTML请求处理器的具体说明

```python
class PluginHTML(BaseModel):
    html: str = Field(..., description="插件主页面")
    is_rendered: bool = Field(False, description="主页面是否已渲染")
    context: Dict[str, Any] = Field({}, description="渲染上下文, 必须可JSON化")
    includes: Dict[str, str] = Field({}, description="单独的css/js文件, key为名称, value为内容")
```

* 桌面端 / Web 均使用`jinja2`进行渲染。若你的页面已经自行渲染，无需`LazyTea`干涉，可以将`is_rendered`设置为 `True`。若设置为`False`，则模板语法需要遵循`jinja2`规范。

* 桌面端 / Web 渲染时允许传入自定义上下文。此外，我们还提供了一些默认上下文：
  * plugin_name  :  插件名称。
  * api_base_url  :  本地服务器的基础url，可用于与后端通信。
  * version  ： `LazyTea`版本号，可用于多版本支持。

##### 如何在HTML中与后端交互的系统性说明

###### 概述

`/api/plugin/{plugin_name}/custom_request` 是一个 `POST` 接口，用于处理插件的自定义请求。该接口与插件的自定义UI页面紧密配合，实现丰富的交互功能。

###### 接口详情

* **路径**: `/api/plugin/{plugin_name}/custom_request`
* **方法**: `POST`
* **参数**:

  * `plugin_name`: 插件名称（路径参数）
  * `body`: 请求体，类型为 `PluginCustomRequest`

    * metthod :  在后端（NoneBot）注册的处理器方法名称
    * pararms ：参数
    * timeout ： 超时时间

    return   在后端（NoneBot）对应处理器返回的原始数据的Json，`LazyTea`不会插手数据格式

  ```python
  class PluginCustomRequest(BaseModel):
      method: str
      params: Dict[str, Any] = Field(default_factory=dict)
      timeout: float = 5.0
  ```

###### 1. UI页面渲染机制

当用户访问插件的自定义UI页面（通过 `/api/plugin/{plugin_name}/custom_html`）时，系统会执行以下步骤：

1. 从后端获取HTML模板和上下文数据。
2. 使用 `Jinja2` 模板引擎渲染页面。
3. 在模板的上下文中，系统会提供以下基础变量：
   * `request`: 当前请求对象
   * `plugin_name`: 插件名称
   * `api_base_url`: API基础URL
   * `version`: 系统版本
   * 以及后端在渲染时返回的任何其他自定义上下文数据。

###### 2. 在UI中发起自定义请求

在你的插件HTML模板中，可以通过 JavaScript 向自定义请求接口发送数据。这是一个完整的示例：

```html
<form id="plugin-form">
    <input type="text" name="param1" placeholder="参数1">
    <input type="text" name="param2" placeholder="参数2">
    <button type="submit">提交</button>
</form>

<script>
document.getElementById('plugin-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());

    try {
        const response = await fetch(`{{ api_base_url }}/api/plugin/{{ plugin_name }}/custom_request`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();
        console.log('插件响应:', result);

        // 处理响应结果
        if (response.ok) {
            alert('操作成功！');
        } else {
            alert('操作失败: ' + result.detail);
        }
    } catch (error) {
        console.error('请求失败:', error);
        alert('请求失败，请检查网络连接');
    }
});
</script>
```

###### 注意事项

* **只读模式检查**: 接口会首先检查系统是否处于只读模式。如果是，请求将被拒绝并返回 `403 Forbidden` 错误。
* **错误处理**: 请务必在前端 JavaScript 代码中妥善处理可能出现的网络错误或API返回的错误响应（如示例代码所示）。
* **模板变量**: 在构建请求URL时，请充分利用模板上下文中提供的 `{{ api_base_url }}` 和 `{{ plugin_name }}` 变量，以确保URL的正确性和可移植性。

<br>

# 🗺️ 项目蓝图 & 生命周期

### **开发蓝图**

* [X]  **赋能开发者**: 提供更完整的接口，让插件与 LazyTea 无缝协作。
* [X]  **远程控制**: 提供独立的 GUI 客户端，允许远程操作您的 Bot 实例。
* [ ]  **极致性能**: 持续优化内存占用，提供更轻快的体验。
* [ ]  **生态合作**: 积极寻求与其他插件开发者的合作，共建 NoneBot 的 UI 生态。
* [X]  **多平台支持**: 探索在移动端支持的可能性。
* [X]  **更完善的用户支持**: 加入QQ群 972526136 以获得进一步支持。

### **版本管理**

本项目遵循 PEP 440 标准。版本号的递增逻辑如下：

* **修订号 (0.0.X)**: 修正 Bug，改进用户体验。
* **次版本号 (0.X.0)**: 引入需要时间验证的较大功能。
* **主版本号 (X.0.0)**: 项目级重构。

> 通常，每个次版本号的正式发布会经过 Alpha (功能实现), Beta (修正错误), rc (发布前排错) 三个阶段。由于精力有限，新版本的 Alpha 发布代表着上一版本停止修订。

---

### **你可能在寻找**（友情链接）

* [LazyTea Client](https://github.com/hlfzsi/LazyTea-Client)：独立的桌面客户端，用于远程连接并管理 LazyTea 后端服务
* [LazyTea Web](https://github.com/hlfzsi/LazyTea-Web)：现代化的 Web 管理界面，支持所有浏览器访问
* [LazyTea Mobile](https://github.com/hlfzsi/LazyTea-mobile)：移动设备专用客户端，随时随地管理机器人
* [NoneBot WebUI](https://webui.nbgui.top/)：✨ 新一代 NoneBot Web 管理界面 ✨
* [nonebot_plugin_lazytea_shell_extension](https://github.com/hlfzsi/nonebot_plugin_lazytea_shell_extension/)：为 LazyTea 启用命令管理，允许通过聊天消息管理权限

<br>

![Star History](https://api.star-history.com/svg?repos=hlfzsi/nonebot_plugin_lazytea,hlfzsi/LazyTea-Client,hlfzsi/LazyTea-Web&type=Date)
