"""
认证相关路由（可选，当前未使用）
"""
from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template
from dashboard.services.config_service import validate_api_keys

bp = Blueprint('auth', __name__)

# 全局变量存储用户配置（保持向后兼容）
user_config = {}


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录配置页面"""
    if request.method == 'POST':
        config = {
            'deepseek_api_key': request.form.get('deepseek_api_key'),
            'okx_api_key': request.form.get('okx_api_key'),
            'okx_secret': request.form.get('okx_secret'),
            'okx_password': request.form.get('okx_password'),
            'wallet_address': request.form.get('wallet_address')
        }
        
        # 验证配置
        if not all([config['deepseek_api_key'], config['okx_api_key'], config['okx_secret'], config['okx_password']]):
            return jsonify({'success': False, 'message': '请填写所有必需的 API 配置'})
        
        # 验证API密钥格式（不进行实际连接）
        if validate_api_keys(config):
            # 保存配置到会话
            session['logged_in'] = True
            session['config'] = config
            global user_config
            user_config = config
            
            return jsonify({'success': True, 'message': '配置成功！正在跳转到 Arena 界面...'})
        else:
            return jsonify({'success': False, 'message': 'API 配置格式验证失败，请检查您的密钥是否正确'})
    
    return render_template('login.html')


@bp.route('/logout')
def logout():
    """登出"""
    session.clear()
    global user_config
    user_config = {}
    return redirect(url_for('index'))
