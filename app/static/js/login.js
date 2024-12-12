document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    try {
        const response = await fetch('/auth/login', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        if (response.ok) {
            localStorage.setItem('token', data.token);
            localStorage.setItem('accounts', JSON.stringify(data.accounts));
            localStorage.setItem('server_id', formData.get('server'));
            window.location.href = '/main';
        } else {
            document.getElementById('error-message').textContent = data.error;
        }
    } catch (error) {
        console.error('Login error:', error);
        document.getElementById('error-message').textContent = '登录失败，请重试';
    }
}); 