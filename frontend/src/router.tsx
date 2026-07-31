import { createBrowserRouter } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import RootLayout from './components/RootLayout'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import PortfolioDetailPage from './pages/PortfolioDetailPage'
import PortfoliosPage from './pages/PortfoliosPage'
import RegisterPage from './pages/RegisterPage'
import UploadPage from './pages/UploadPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: '/',
        element: <RootLayout />,
        children: [
          { index: true, element: <PortfoliosPage /> },
          { path: 'upload', element: <UploadPage /> },
          { path: 'portfolios/:id', element: <PortfolioDetailPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
])
