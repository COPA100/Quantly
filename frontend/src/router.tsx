import { createBrowserRouter } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import RootLayout from './components/RootLayout'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import HoldingsTab from './pages/portfolio/HoldingsTab'
import OverviewTab from './pages/portfolio/OverviewTab'
import PortfolioLayout from './pages/portfolio/PortfolioLayout'
import RiskTab from './pages/portfolio/RiskTab'
import { FactorsTab, OptimizeTab, StressTab } from './pages/portfolio/SectionTabs'
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
          {
            path: 'portfolios/:id',
            element: <PortfolioLayout />,
            children: [
              { index: true, element: <OverviewTab /> },
              { path: 'risk', element: <RiskTab /> },
              { path: 'stress', element: <StressTab /> },
              { path: 'optimize', element: <OptimizeTab /> },
              { path: 'factors', element: <FactorsTab /> },
              { path: 'holdings', element: <HoldingsTab /> },
            ],
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
])
