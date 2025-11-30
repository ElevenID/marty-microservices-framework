import { useState } from 'react';
import { LoginForm } from './components/LoginForm';
import { Profile } from './components/Profile';

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));

  const handleLoginSuccess = (newToken: string) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Identity Manager
          </h1>
        </div>
      </header>
      <main>
        {token ? (
          <Profile token={token} onLogout={handleLogout} />
        ) : (
          <LoginForm onLoginSuccess={handleLoginSuccess} />
        )}
      </main>
    </div>
  );
}

export default App;
