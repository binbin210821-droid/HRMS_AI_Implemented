import { useParams } from 'react-router-dom'

import { FadeIn } from '../components/animations/index.js'
import MainLayout from '../components/layout/MainLayout.jsx'
import { useAuthStore } from '../stores/authStore.js'

const SECTION_CONTENT = {
  manager: {
    performance: {
      title: 'Hiệu suất nhân viên',
      description: 'Theo dõi kết quả và tiến độ của nhân sự trong phòng ban.',
    },
    assistant: {
      title: 'Trợ lý AI',
      description: 'Không gian hỗ trợ quản lý phân tích và lập kế hoạch hành động.',
    },
  },
  leadership: {
    performance: {
      title: 'Hiệu suất toàn công ty',
      description: 'Tổng quan hiệu suất nhân sự trên toàn doanh nghiệp.',
    },
    departments: {
      title: 'Phòng ban & nhân viên',
      description: 'Quản lý phòng ban và xem nhân viên theo từng phòng khi cần.',
    },
    alerts: {
      title: 'Cảnh báo toàn công ty',
      description: 'Theo dõi các cảnh báo cần ưu tiên ở cấp độ toàn doanh nghiệp.',
    },
    managers: {
      title: 'Đánh giá quản lý',
      description: 'Theo dõi chất lượng quản trị và kết quả của các phòng ban.',
    },
    assistant: {
      title: 'Trợ lý AI',
      description: 'Không gian hỗ trợ lãnh đạo tổng hợp thông tin toàn công ty.',
    },
  },
}

function WorkspaceSectionPage() {
  const { section } = useParams()
  const { role } = useAuthStore()
  const content = SECTION_CONTENT[role]?.[section] || {
    title: 'Không gian làm việc',
    description: 'Nội dung đang được chuẩn bị.',
  }

  return (
    <MainLayout>
      <FadeIn className="mx-auto max-w-6xl">
        <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200 sm:p-8">
          <p className="!text-caption !font-semibold !uppercase !tracking-wider !text-brand-600">
            WorkMind
          </p>
          <h1 className="mt-2 text-slate-900">{content.title}</h1>
          <p className="mt-3 max-w-2xl text-ink-600">{content.description}</p>
        </section>
      </FadeIn>
    </MainLayout>
  )
}

export default WorkspaceSectionPage
