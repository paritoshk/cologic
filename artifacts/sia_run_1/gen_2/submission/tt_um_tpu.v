module tt_um_tpu (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);
    reg signed [7:0] a [0:3];
    reg signed [7:0] b [0:3];

    wire load_en = uio_in[0];
    wire load_sel_b = uio_in[1];
    wire [1:0] load_index = uio_in[3:2];
    wire output_en = uio_in[4];
    wire [1:0] output_sel = uio_in[6:5];

    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < 4; i = i + 1) begin
                a[i] <= 8'sd0;
                b[i] <= 8'sd0;
            end
        end else if (load_en) begin
            if (load_sel_b)
                b[load_index] <= ui_in;
            else
                a[load_index] <= ui_in;
        end
    end

    wire row = output_sel[1];
    wire col = output_sel[0];

    wire signed [15:0] prod0 = a[{row, 1'b0}] * b[{1'b0, col}];
    wire signed [15:0] prod1 = a[{row, 1'b1}] * b[{1'b1, col}];
    wire signed [15:0] sum   = prod0 + prod1;

    wire [7:0] selected = sum[7:0];

    assign uo_out = output_en ? selected : 8'd0;
    assign uio_out = {output_en, 7'b0};
    assign uio_oe = 8'b1000_0000;

    wire _unused = &{ena, uio_in[7]};
endmodule
