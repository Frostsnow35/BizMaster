/**
 * @brief 错误消息友好化工具
 *
 * 将后端技术错误消息映射为中小商户可理解的友好提示，
 * 包含问题解释 + 建议操作。
 */

/** 错误映射条目 */
interface ErrorMapping {
  /** 匹配模式（正则或关键词） */
  pattern: RegExp
  /** 友好的标题 */
  title: string
  /** 详细解释 */
  description: string
  /** 建议操作 */
  suggestions: string[]
}

const ERROR_MAPPINGS: ErrorMapping[] = [
  {
    pattern: /缺少(金额|客户ID|订单ID|日期|成本|销量|库存|状态|广告花费|新客户)列/,
    title: '数据缺少必要字段',
    description: '您上传的数据中缺少分析所需的字段。这可能是因为您导出的数据不完整，或列名与系统预期不一致。',
    suggestions: [
      '请检查您的 Excel/CSV 文件，确保包含了完整的订单信息',
      '如使用电商平台导出功能，建议选择"导出全部字段"而非"导出选中字段"',
      '点击"数据管理"页面的数据详情，查看当前数据包含哪些列',
    ],
  },
  {
    pattern: /不支持的 operation/,
    title: '分析类型暂不支持',
    description: '您请求的分析类型暂时无法执行。这通常是因为分析的具体指标在您的数据中缺少支撑字段。',
    suggestions: [
      '试试换一种表述方式重新提问，例如将"对比增长率"改为"本月的销售额是多少"',
      '确认数据中是否包含进行该分析所需的所有字段',
    ],
  },
  {
    pattern: /数据源为空/,
    title: '数据内容为空',
    description: '您选择的数据源中没有可分析的数据。这可能是因为上传的文件内容为空。',
    suggestions: [
      '前往"数据管理"页面确认该数据源的行数是否大于 0',
      '如果行数为 0，请重新上传包含数据的文件',
    ],
  },
  {
    pattern: /Agent 执行异常|Agent 执行崩溃/,
    title: '分析过程出现异常',
    description: 'AI 分析引擎在处理您的请求时遇到了技术问题。这通常是临时的，不影响您的数据安全。',
    suggestions: [
      '请稍后重试，或换个更简单的问题试试',
      '如果问题持续出现，请检查网络连接是否稳定',
      '确认系统设置中的 API Key 是否有效',
    ],
  },
  {
    pattern: /JOIN 查询执行失败|关联.*失败|加载关联表.*失败/,
    title: '数据关联失败',
    description: '尝试将多个数据表关联起来时遇到了问题。可能的原因是不同表中的关联字段不匹配。',
    suggestions: [
      '确保要关联的两个表格有共同的字段（如"订单号"）',
      '检查字段中的值是否格式一致（如日期格式统一）',
    ],
  },
  {
    pattern: /计算过程中发生异常/,
    title: '指标计算出错',
    description: '在计算电商指标时遇到了数据问题。通常是某些数据值为空或格式不正确。',
    suggestions: [
      '检查数据中金额、数量等数值列是否包含文本或特殊字符',
      '确认数据中"实付金额"等列的值都是数字格式',
    ],
  },
  {
    pattern: /文件解析失败/,
    title: '文件格式不正确',
    description: '上传的文件无法被正确识别。文件格式可能存在问题。',
    suggestions: [
      '请确保上传的是 CSV 或 Excel（.xlsx/.xls）格式',
      '检查文件是否有损坏，可以尝试重新下载后再上传',
      'CSV 文件请确保第一行是列名（表头）',
    ],
  },
  {
    pattern: /数据入库失败/,
    title: '数据存储失败',
    description: '数据已成功解析，但在保存到本地数据库时出现了问题。',
    suggestions: [
      '请检查磁盘空间是否充足',
      '关闭其他分析窗口后重试',
      '重启应用后再上传',
    ],
  },
  {
    pattern: /API Key 未配置|API.?Key.*未/,
    title: 'AI 服务未配置',
    description: '系统尚未配置 AI 服务的访问密钥（API Key），无法进行智能分析。',
    suggestions: [
      '前往"系统设置"页面填写 DeepSeek API Key',
      '访问 platform.deepseek.com 注册并获取 API Key',
      '支持支付宝充值，最低 1 元即可开始使用',
    ],
  },
  {
    pattern: /Network Error|ECONNREFUSED|timeout|连接失败/,
    title: '网络连接异常',
    description: '与后端服务的连接出现了问题。可能是服务未启动或网络不稳定。',
    suggestions: [
      '请确认后端服务是否已启动（运行 scripts/dev.bat）',
      '检查防火墙是否拦截了本地端口 8000',
      '尝试重启应用',
    ],
  },
  {
    pattern: /收到非预期的工具返回|tool.*not found|工具.*不存在/,
    title: '分析能力受限',
    description: 'AI 尝试使用了不支持的分析方式。系统会自动调整策略。',
    suggestions: [
      '尝试换一种方式描述您的问题',
      '避免使用过于技术化的术语（如"请执行 SQL 查询"）',
    ],
  },
]

/**
 * @brief 将后端错误消息转换为友好的用户提示
 * @param rawError 原始错误消息
 * @returns 友好提示对象，或 null（无法识别时）
 */
export function translateError(rawError: string): { title: string; description: string; suggestions: string[] } | null {
  if (!rawError) return null

  for (const mapping of ERROR_MAPPINGS) {
    if (mapping.pattern.test(rawError)) {
      return {
        title: mapping.title,
        description: mapping.description,
        suggestions: mapping.suggestions,
      }
    }
  }

  return null
}

/**
 * @brief 格式化错误消息为显示用的字符串
 * @param rawError 原始错误消息
 * @returns 格式化后的文本（可识别时返回友好提示，否则返回原文截断）
 */
export function formatError(rawError: string): string {
  const translated = translateError(rawError)
  if (translated) {
    const parts = [
      `【${translated.title}】`,
      translated.description,
      '',
      '您可以：',
      ...translated.suggestions.map((s) => `  • ${s}`),
    ]
    return parts.join('\n')
  }

  // 无法识别时，截断过长的原始消息
  if (rawError.length > 500) {
    return rawError.substring(0, 497) + '...'
  }
  return rawError
}
