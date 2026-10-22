import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppRouter } from './layout/AppRouter';
import './styles/landing.css';
import './styles/admin.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppRouter />
  </React.StrictMode>,
);
