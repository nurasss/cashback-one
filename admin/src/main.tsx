import React from 'react';
import ReactDOM from 'react-dom/client';
import { AdminProvider } from './auth/provider';
import { AppRouter } from './layout/AppRouter';
import './styles/admin.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><AdminProvider><AppRouter /></AdminProvider></React.StrictMode>,
);
