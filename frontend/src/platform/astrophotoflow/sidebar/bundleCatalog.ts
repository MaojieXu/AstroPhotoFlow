import type { NodeCapability } from '@astrophotoflow/ui'
import { shallowReactive } from 'vue'

export const bundleCapabilities = shallowReactive(new Map<string, NodeCapability>())
