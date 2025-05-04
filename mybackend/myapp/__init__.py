# D:\bkgg\mybackend\myapp\__init__.py

# 指定當 Django 加載 myapp 時，應該使用的 AppConfig 類。
# 這會確保我們修改過的 MyappConfig (包含 ready 方法) 被使用。
default_app_config = 'myapp.apps.MyappConfig'