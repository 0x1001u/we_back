# 微信云托管部署指南

## 📋 部署前准备

### 1. 微信小程序准备
- 已注册微信小程序账号
- 获取小程序的 AppID 和 AppSecret
- 开通微信云托管服务

### 2. 数据库准备
- 在微信云托管控制台创建 MySQL 数据库实例
- 记录数据库连接信息（主机、端口、用户名、密码、数据库名）

## 🚀 部署步骤

### 第一步：创建云托管服务
1. 登录微信云托管控制台
2. 点击"新建服务"
3. 选择合适的地域和计费方式
4. 填写服务名称（如：room-booking-backend）

### 第二步：配置环境变量
在服务的"环境变量"页面添加以下配置：

```bash
# 必需配置
NODE_ENV=production
JWT_SECRET=your-super-secret-jwt-key-change-me
WECHAT_APP_ID=your_wechat_app_id
WECHAT_APP_SECRET=your_wechat_app_secret

# 数据库配置（根据实际情况填写）
DB_HOST=your_db_host
DB_PORT=3306
DB_NAME=room_booking
DB_USER=your_db_user
DB_PASSWORD=your_db_password

# 可选配置
CLOUD_ENV_ID=your_cloud_env_id
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE=10485760
```

### 第三步：部署代码

#### 方式一：Git 仓库部署（推荐）
1. 将代码推送到 Git 仓库（GitHub/GitLab/腾讯工蜂等）
2. 在云托管控制台选择"从代码仓库部署"
3. 配置仓库地址和分支
4. 设置构建目录为 `wechat-miniprogram-backend`
5. 确认 Dockerfile 路径正确

#### 方式二：代码包上传
1. 将 `wechat-miniprogram-backend` 目录打包为 zip 文件
2. 在云托管控制台选择"上传代码包"
3. 上传 zip 文件并部署

### 第四步：验证部署
1. 部署完成后，访问服务的健康检查接口：
   ```
   GET https://your-service-url/health
   ```

2. 预期返回：
   ```json
   {
     "code": 0,
     "message": "success",
     "data": {
       "status": "healthy",
       "service": "xinghui",
       "environment": "production"
     }
   }
   ```

3. 检查 API 文档：
   ```
   https://your-service-url/docs
   ```

## 🏗️ 功能说明

### 自动初始化
后端服务在启动时会自动：
- ✅ 创建所有必需的数据库表
- ✅ 初始化棋牌室示例数据（店面和包间信息）
- ✅ 检查并添加缺失的数据库字段

### 核心功能模块
- 🏪 **店面管理**：店面信息展示和管理
- 🏠 **包间管理**：包间列表、详情、搜索和筛选
- 📅 **预订系统**：创建预订、查询预订、取消预订
- ⭐ **评价系统**：用户评价、商家回复
- 👤 **用户管理**：微信登录、用户信息管理
- 💰 **支付功能**：微信支付集成

### API 接口
所有 API 接口都支持：
- RESTful 设计
- 完整的数据验证
- 统一的错误处理
- 自动生成的 API 文档

## 🛠️ 开发调试

### 本地开发环境
```bash
cd wechat-miniprogram-backend
pip install -r requirements.txt
python run.py
```

### 查看日志
在云托管控制台的"实例日志"中查看应用运行日志

### 数据库管理
建议使用数据库管理工具连接云数据库进行数据查看和管理

## 🔧 常见问题

### 1. 数据库连接失败
- 检查数据库配置是否正确
- 确认数据库实例已启动
- 验证网络连接

### 2. 微信接口调用失败
- 检查 WECHAT_APP_ID 和 WECHAT_APP_SECRET 是否正确
- 确认小程序已发布或在开发者工具中测试

### 3. JWT 相关错误
- 确保 JWT_SECRET 已正确配置且足够复杂
- 检查 JWT 过期时间设置

### 4. 文件上传问题
- 检查 UPLOAD_DIR 目录是否存在
- 验证文件大小是否超过限制

## 📞 技术支持

如遇到部署问题，请检查：
1. 云托管控制台的实例日志
2. 数据库连接状态
3. 环境变量配置
4. 网络和安全组设置

## 🎯 下一步

部署成功后，您可以：
1. 配置前端小程序连接到后端服务
2. 自定义店面和包间信息
3. 配置微信支付功能
4. 添加更多业务逻辑

---

🎉 **恭喜！您的棋牌室预订系统后端已成功部署到微信云托管！**