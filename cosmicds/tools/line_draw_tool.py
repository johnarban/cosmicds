from bqplot.marks import Lines, Scatter
from bqplot_image_gl.interacts import MouseInteraction, mouse_events
from echo import CallbackProperty
from glue.config import viewer_tool
from glue_jupyter.bqplot.common.tools import InteractCheckableTool
from traitlets import Unicode, HasTraits

@viewer_tool
class LineDrawTool(InteractCheckableTool, HasTraits):

    tool_id = 'cds:linedraw'
    action_text = 'Draw line'
    draw_tool_tip = 'Draw a trend line'
    update_tool_tip = 'Update trend line'
    tool_tip = Unicode().tag(sync=True)
    mdi_icon = "mdi-message-draw"
    line_drawn = CallbackProperty(False)

    def __init__(self, viewer, bx=0, by=0, **kwargs):
        super().__init__(viewer, **kwargs)
        self.tool_tip = self.draw_tool_tip
        self.line_drawn = False
        self.line = None
        self.endpoint = None
        self._follow_cursor = False
        self.bx = bx
        self.by = by

        figure = viewer.figure
        self._original_interaction = figure.interaction
        #scales_image = figure.marks[0].scales
        scales_image = viewer.scales
        self._interaction = MouseInteraction(x_scale=scales_image['x'], y_scale=scales_image['y'], move_throttle=70, next=None,
                                events=mouse_events)
        self._interaction.on_msg(self._message_handler)

    def _message_handler(self, interaction, data, buffers):
        event_type = data['event']
        if event_type == 'mousemove':
            self._handle_mousemove(data)
        elif event_type == 'click':
            self._handle_click(data)

    def _handle_mousemove(self, data):
        figure = self.viewer.figure
        image = figure.marks[0]

        # Note that, since the image scales of the glue-jupyter scatter viewer are from 0 to 1
        # we don't need to worry about any normalization
        # If this weren't the case, we could grab the normalized coordinates via
        # 
        # image = self.viewer.figure.marks[0]
        # normalized_x = (domain_x - image.x[0]) / (image.x[1] - image.x[0])
        # normalized_y = (domain_y - image.y[0]) / (image.y[1] - image.y[0])
        domain = data['domain']
        x, y = domain['x'], domain['y']

        if self.line is None:
            self.line = Lines(x=[self.bx, self.viewer.state.x_max], y=[self.bx, self.by], scales=image.scales, colors=['black'])
            figure.marks = figure.marks + [self.line]
            self._follow_cursor = True
            
        if self._follow_cursor:
            self.line.x = [self.bx, x]
            self.line.y = [self.by, y]

    def _handle_click(self, data):
        if self._follow_cursor:

            figure = self.viewer.figure

            # Clear the old endpoint
            domain = data['domain']
            x, y = domain['x'], domain['y']
            figure.marks = [mark for mark in figure.marks if mark is not self.endpoint]
            
            # Add a new one
            image = figure.marks[0]
            endpoint = Scatter(x=[x],
                              y=[y],
                              colors=['black'],
                              scales = {'x': image.scales['x'], 'y': image.scales['y']},
                              interactions = {'click':'select'}
                            )
            endpoint.on_drag_start(self._on_endpoint_drag_start)
            endpoint.on_drag(self._on_endpoint_drag)
            endpoint.on_drag_end(self._on_endpoint_drag_end)
            #endpoint.opacities = [0]
            endpoint.hovered_style = {'cursor' : 'grab'}
            endpoint.enable_move = True
            figure.marks = figure.marks + [endpoint]
            self.endpoint = endpoint
            self.line_drawn = True
            self.tool_tip = self.update_tool_tip

            # End drawing
            self.deactivate()

    def _on_endpoint_drag_start(self, element, event):
        self.endpoint.hovered_style = {'cursor' : 'grabbing'}

    def _on_endpoint_drag_end(self, element, event):
        x = self.endpoint.x[0]
        y = self.endpoint.y[0]
        x_adj, y_adj = self._coordinates_in_bounds(x,y)
        if x_adj != x or y_adj != y:
            self.line.x = [self.bx, x_adj]
            self.line.y = [self.by, y_adj]
            self.endpoint.x = [x_adj]
            self.endpoint.y = [y_adj]

    def _on_image_hover(self, element, event):
        if self.endpoint is not None:
            self.endpoint.opacities = [1]

    def _on_endpoint_drag(self, element, event):
        point = event["point"]
        x, y = point["x"], point["y"]
        self.line.x = [self.bx, x]
        self.line.y = [self.by, y]

    def _update_interaction(self):
        have_endpoint = self.endpoint is not None

        # if have_endpoint:
        #     self.endpoint.opacities = [int(draw_on)]
        #     self.endpoint.hovered_style = {'cursor' : 'grab'} if draw_on else {}
        #     self.endpoint.enable_move = draw_on

        if have_endpoint:
            self.viewer.figure.interaction = None
        else:
            self.viewer.figure.interaction = self._interaction
        
    def activate(self):
        self._update_interaction()

    def deactivate(self):
        self._follow_cursor = False
        self.viewer.figure.interaction = self._original_interaction
        self.viewer.toolbar.active_tool = None

        # Make sure that we can't end up with the line defined but not the endpoint
        if self.line is not None and self.endpoint is None:
            fig = self.viewer.figure
            fig.marks = [m for m in fig.marks if m != self.line]
            self.line = None
            self.tool_tip = self.draw_tool_tip

    def close(self):
        super().close()

    def _coordinates_in_bounds(self, x, y):
        """
        If a student drags the endpoint beyond the viewer bounds, we want to bring it back inside.
        This function, given x and y coordinates of a chosen endpoint, finds the
        coordinates of the point where their line crosses the boundary of the viewer.
        """

        # Get the current viewer bounds
        state = self.viewer.state
        x_min, x_max, y_min, y_max = state.x_min, state.x_max, state.y_min, state.y_max

        # If the point is in bounds, do nothing
        if x >= x_min and x <= x_max and y >= y_min and y <= y_max:
            return x, y

        # Vertical line
        if x == self.bx:
            y_adj = y_min if y < y_min else y_max
            return x, y_adj

        # Horizontal line
        if y == self.by:
            x_adj = x_min if x < x_min else x_max
            return x_adj, y

        # Length of the vector from the basepoint to the endpoint

        t1 = (x_max - self.bx) / (x - self.bx)
        t2 = (y_max - self.by) / (y - self.by)
        t3 = (x_min - self.bx) / (x - self.bx)
        t4 = (y_min - self.by) / (y - self.by)
        ts = [t for t in [t1,t2,t3,t4] if t > 0 and t < 1]
        t = min(ts or [0]) * 0.98

        return x * t, y * t


    def clear(self):
        if self.line is None and self.endpoint is None:
            return
        figure = self.viewer.figure
        to_remove = [x for x in [self.line, self.endpoint] if x is not None]
        figure.marks = [mark for mark in figure.marks if mark not in to_remove]
        self.line = None
        self.endpoint = None
        self.line_drawn = False
