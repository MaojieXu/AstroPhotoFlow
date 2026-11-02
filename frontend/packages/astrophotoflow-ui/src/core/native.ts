import { zCanvasGraphRequest } from '../generated/api/zod.gen'

export const canvasEditSchema=zCanvasGraphRequest.shape.edit

export {
 zCanvasPageState as canvasPageSchema,
 zCanvasAddRequest as canvasAddRequestSchema,
 zCanvasAddResult as canvasAddResultSchema,
 zNativeCanvasGraphCommand as canvasGraphCommandSchema,
 zNativeCanvasMessage as canvasCommandSchema,
 zNativePageReply as nativePageReplySchema
} from '../generated/api/zod.gen'
export type {
 CanvasPageState as CanvasPage,
 CanvasAddResult,
 NativeCanvasGraphCommand as CanvasGraphCommand,
 NativeCanvasMessage as CanvasCommand,
 NativeCanvasEvent as CanvasEvent,
 NativePageReply
} from '../generated/api/types.gen'
